import asyncio
import json
import random
import datetime
import os, sys
import random
import logging
from contextlib import ExitStack, contextmanager, asynccontextmanager
from types import TracebackType
from typing import List, Dict, Any, Awaitable, Type, Generic, TypeVar, ContextManager
from collections.abc import Callable

from .models import OnMessageConfig, OnOpenConfig
from .session import StreamSession
from .exceptions import CloseSessionException, CloseStreamException
from .connection import AbstractConnection, AbstractClient, AbstractChannel, Message, BaseStartArgs, WebsocketClient, ClientConf, ServerConf
from miniappi.config import settings
from rich import print
from rich.panel import Panel

type RequestStreams = List[Callable[[dict], Awaitable[Any]]]

type CloseCallbackWithError = Callable[[type[BaseException], BaseException, TracebackType], Awaitable[Any]]
type CloseCallbackNoError = Callable[[None, None, None], Awaitable[Any]]
type CloseCallback = CloseCallbackWithError | CloseCallbackNoError

StreamSessionT = TypeVar("StreamSessionT", bound=StreamSession, default=StreamSession)
#ConnectionClientT = TypeVar("ConnectionClientT", bound=AbstractConnectionClient)

class Streamer(Generic[StreamSessionT]):

    cls_session: Type[StreamSessionT] = StreamSession

    conn_client: AbstractClient = WebsocketClient()

    def __init__(self, channel: str | None):
        self.url = channel

        self.callbacks_start = []
        self.callbacks_message: List[Callable[[Message], Awaitable[Any]]] = []
        self.callbacks_open: List[Callable[[StreamSessionT], Awaitable[Any]]] = []
        self.callbacks_close: List[CloseCallback] = []
        self.callbacks_end: List[CloseCallback] = []

        self.app_context_managers: List[ContextManager] = []
        self.channel_context_managers: List[ContextManager] = []

        self.sessions: Dict[str, StreamSessionT] = {}

        self.subscribed = False

    def get_app_context_managers(self, args: dict):
        return self.app_context_managers

    def get_channel_context_managers(self, session: StreamSessionT):
        return self.channel_context_managers

    def show_app_url(self, url: str):
        print(
            Panel(
                "Miniappi is running.\n"
                f"[bold red]App link:[/bold red] [link={url}]{url}[/link]"
            )
        )

    @asynccontextmanager
    async def _subscribe(self, echo_link: bool | None, stack: ExitStack):
        client: AbstractChannel = self.conn_client.from_init_channel(self.url)
        async with client.connect() as connection:
            config: ServerConf = await connection.init_app(
                ClientConf(version=settings.version)
            )
            url = config.app_url
            show_url = (
                echo_link
                if echo_link is not None
                else settings.echo_url
            )
            if show_url:
                self.show_app_url(url)
            args = {
                "app_url": config.app_url,
                "name": config.app_name
            }
            for app_context in self.get_app_context_managers(args):
                stack.enter_context(app_context)
            yield connection

    async def _listen_start(self, connection: AbstractConnection):
        async for start_args in connection.listen_start():
            yield start_args

    def run(self, echo_link: bool | None = None):
        "Run app (sync)"
        asyncio.run(self.start(echo_link=echo_link))

    async def start(self, echo_link: bool | None = None):
        "Start app async"
        if self.subscribed:
            raise StreamRunningError("Stream is already subscribed")
        logger = self.get_logger("stream")

        with ExitStack() as app_stack:
            try:
                logger.debug(f"Subscribing stream: {self.url}")
                async with self._subscribe(echo_link, stack=app_stack) as start_conn:
                    self.subscribed = True
                    logger.info(f"Stream subscribed: {self.url}")
                    async with asyncio.TaskGroup() as tg:
                        await self._run_start(tg)
                        async for start_args in self._listen_start(start_conn):
                            tg.create_task(self.open_session(start_conn, start_args))
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
                self.subscribed = False

    async def open_session(self, start_conn: AbstractConnection, start_args: BaseStartArgs):
        logger = self.get_logger("session")

        client = self.conn_client.from_start_args(start_args)
        async with client.connect() as conn:
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
        def wrapper(func: Callable[[StreamSessionT], Awaitable[Any]]):
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
        def wrapper(func: Callable[[StreamSessionT], Awaitable[Any]]):
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
