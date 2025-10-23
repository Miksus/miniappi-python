import asyncio
import sys
import logging
from dataclasses import asdict
from contextlib import ExitStack, contextmanager
from types import TracebackType
from typing import List, Dict, Any, Awaitable, Type, Generic, TypeVar, ContextManager
from functools import partial
from collections.abc import Callable

from miniappi.core.models.callbacks import OnMessageConfig, OnOpenConfig
from miniappi.core.exceptions import CloseSessionException, CloseStreamException
from . import connection as conn
from .connection import Message, ServerConf, ClientConf, UserSessionArgs
from miniappi.config import settings
from miniappi.core.models.context import Context
from miniappi.core.context import app_context as default_app_context, user_context as default_user_context
from .session import Session

from rich import print
from rich.panel import Panel

type RequestStreams = List[Callable[[dict], Awaitable[Any]]]

type CloseCallbackWithError = Callable[[type[BaseException], BaseException, TracebackType], Awaitable[Any]]
type CloseCallbackNoError = Callable[[None, None, None], Awaitable[Any]]
type CloseCallback = CloseCallbackWithError | CloseCallbackNoError


class App:
    """Miniappi application

    This class is the entrypoint
    to create apps and it handles
    the communication with Miniappi
    server.

    Args:
        app_name (str, optional):
            Name of the application. None for
            anonymous applications. Does nothing
            currently but exists for forward
            compatibility.
        user_context (Context, optional): 
            Optional extra user scoped context
            to keep track on user level
            data. This is automatically
            scoped and can be set globally.
        app_context (Context, optional):
            Optional app scoped context
            to keep track on app level data.
            This is automatically
            scoped and can be set globally.

    Examples:
        ```python
        from miniappi import App

        app = App()

        @app.on_open()
        async def new_user(session):
            print("New user joined")
            ...

        app.run()
        ```
    """

    cls_session: Type[Session] = Session

    conn_client: conn.base.AbstractClient = conn.websocket.WebsocketClient()

    def __init__(self, app_name: str | None = None,
                 user_context: Context | None = None,
                 app_context: Context | None = None):
        self.app_name = app_name

        self.callbacks_start = []
        self.callbacks_message: List[Callable[[Message], Awaitable[Any]]] = []
        self.callbacks_open: List[Callable[..., Awaitable[Any]]] = []
        self.callbacks_close: List[CloseCallback] = []
        self.callbacks_end: List[CloseCallback] = []

        self.app_context_managers: List[ContextManager] = []
        self.channel_context_managers: List[ContextManager] = []

        self.sessions: Dict[str, Session] = {}
        self.is_running = False

        self.channel_context = user_context
        self.app_context = app_context

    def _get_client_config(self):
        return ClientConf(
            app_name=self.app_name,
            version=settings.version
        )

    def get_channel_context_managers(self, session: Session):
        init_args = dict(
            session=session,
            request_id=session.start_args.request_id,
        )
        ctx = [
            *self.channel_context_managers,
            default_user_context.enter(
                init_args
            ),
        ]
        if self.channel_context:
            ctx.append(self.channel_context.enter())
        return ctx

    def get_app_context_managers(self, conf: ServerConf):
        init_args = dict(
            app=self,
            sessions=self.sessions,
            **asdict(conf)
        )
        ctx = [
            *self.app_context_managers,
            default_app_context.enter(init_args),
        ]
        if self.app_context:
            ctx.append(self.app_context.enter())
        return ctx


    def show_app_running(self, server_conf: ServerConf):
        url = server_conf.app_url
        print(
            Panel(
                "Miniappi is running.\n"
                f"[bold red]App link:[/bold red] [link={url}]{url}[/link]"
            )
        )

    async def setup_start(self, server_conf: ServerConf, echo_link: bool, task_group: asyncio.TaskGroup, stack: ExitStack):
        if echo_link:
            self.show_app_running(server_conf)
        for app_context in self.get_app_context_managers(server_conf):
            stack.enter_context(app_context)
        self.is_running = True
        self.app_name = server_conf.app_name
        await self._run_start(task_group)

    async def _listen_start(self, echo_link: bool | None, app_stack: ExitStack, task_group: asyncio.TaskGroup):
        app_config = self._get_client_config()

        setup_start = partial(self.setup_start, echo_link=echo_link, stack=app_stack, task_group=task_group)
        async for msg in self.conn_client.listen_app(app_config, setup_start=setup_start):
            yield msg

    def run(self, echo_link: bool | None = None):
        "Run app (sync)"
        asyncio.run(self.start(echo_link=echo_link))

    async def start(self, echo_link: bool | None = None):
        "Start app async"
        logger = self.get_logger("init")

        with ExitStack() as app_stack:
            try:
                async with asyncio.TaskGroup() as tg:
                    async for start_args in self._listen_start(echo_link=echo_link, app_stack=app_stack, task_group=tg):
                        tg.create_task(self.open_session(start_args))
            except ExceptionGroup as exc:
                # Exception is ExceptionGroup[ExceptionGroup]
                # Check if all expected
                await self._run_end()
                is_expected = True
                for channel_exc in exc.exceptions:
                    if isinstance(channel_exc, ExceptionGroup):
                        for session_exc in channel_exc.exceptions:
                            if not isinstance(session_exc, CloseStreamException):
                                is_expected = False
                                break
                    else:
                        is_expected = False
                        break
                if not is_expected:
                    logger.exception("Stream closed unexpectedly")
                    raise
                logger.info("Stream closed expectedly")
            else:
                await self._run_end()
            finally:
                self.is_running = False

    async def open_session(self, start_args: UserSessionArgs):
        logger = self.get_logger("session")
        async with self.conn_client.connect_user(start_args) as conn:
            session = self.cls_session(
                start_conn=conn,
                start_args=start_args,
                callbacks_message=self.callbacks_message,

                sessions=self.sessions
            )

            with ExitStack() as channel_stack:
                for channel_context in self.get_channel_context_managers(session):
                    channel_stack.enter_context(channel_context)
                try:
                    async with asyncio.TaskGroup() as tg:
                        session.tasks.append(tg.create_task(session.listen()))
                        for stream in self.callbacks_open:
                            args = []
                            if stream.pass_session:
                                args.append(session)
                            session.tasks.append(tg.create_task(stream(*args)))
                        logger.info(f"Session opened for client: {start_args.request_id}")
                except ExceptionGroup as exc:
                    is_close_stream = all(isinstance(e, CloseStreamException) for e in exc.exceptions)
                    if is_close_stream:
                        logger.info("Stream closed expectedly")
                        # We raise so that stream can close itself
                        raise
                    is_expected = all(isinstance(e, CloseSessionException) for e in exc.exceptions)
                    if not is_expected:
                        logger.exception("Session closed with error")
                        raise
                    # Stream closed expectedly
                    logger.info("Session closed expectedly")
                finally:
                    await self._run_close()
                    await session.close()

    async def _run_start(self, tg: asyncio.TaskGroup):
        for cb in self.callbacks_start:
            tg.create_task(cb())

    async def _run_end(self):
        for cb in self.callbacks_end:
            await cb(*sys.exc_info())

    async def _run_close(self):
        for cb in self.callbacks_close:
            await cb(*sys.exc_info())

    def get_logger(self, name: str):
        name = f".{name}" if name else ""
        return logging.getLogger(__name__ + name)

    @contextmanager
    def temp(self):
        """Temporarily set callbacks to the app
        
        This is useful for syncing other sessions

        Examples
        --------
        ```python
        async with app.temp() as temp:

            @temp.on_open()
            async def new_users(session):
                ...

            # Callback "new_users" will called
            # now for all new user sessions
            ...

        # Callback "new_users" won't be called
        # anymore
        ...
        ```
        """
        from miniappi.flow.app import temp_app
        with temp_app(self) as t:
            yield t

    def on_message(self):
        """Callback for user sending a message (data).

        Examples
        --------
        ```python
        @app.on_message()
        async def new_message(msg):
            ...
        ```
        """
        def wrapper(func: Callable[[dict], Awaitable[Any]]):
            self.callbacks_message.append(
                OnMessageConfig(
                    func=func,
                )
            )
            return func
        return wrapper

    def on_start(self):
        """Callback for the app starting.

        Examples
        --------
        ```python
        @app.on_start()
        async def app_start():
            ...
        ```
        """
        def wrapper(func: Callable[..., Awaitable[Any]]):
            self.callbacks_start.append(func)
            return func
        return wrapper

    def on_open(self, pass_session=False):
        """Callback for user opening an app
        session (user connected to the app)

        Examples
        --------
        ```python
        @app.on_open()
        async def new_user(session):
            ...
        ```
        """
        def wrapper(func: Callable[..., Awaitable[Any]]):
            self.callbacks_open.append(
                OnOpenConfig(
                    func=func,
                    pass_session=pass_session
                )
            )
            return func
        return wrapper

    def on_close(self):
        """Callback for user closing the
        app session (user left the app).

        Examples
        --------
        ```python
        @app.on_close()
        async def user_left(exc_type, exc, tb):
            ...
        ```
        """
        def wrapper(func: CloseCallback) -> CloseCallback:
            self.callbacks_close.append(func)
            return func
        return wrapper

    def on_end(self):
        """Callback for app shutting down.

        Examples
        --------
        ```python
        @app.on_end()
        async def app_shutdown(exc_type, exc, tb):
            ...
        ```
        """
        def wrapper(func: CloseCallback):
            self.callbacks_end.append(func)
            return func
        return wrapper
