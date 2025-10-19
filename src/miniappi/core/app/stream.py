import logging

from miniappi.core.context import Context

from miniappi.core.stream.base import Streamer
from miniappi.core.stream.session import StreamSession
from .models import BaseMessage, BaseContent
from .message_types import InputMessage, PutRoot

from .context import user_context as default_channel_context, app_context as default_app_context
from .utils.message import handle_message
from .session import AppSession

logger = logging.getLogger(__name__)

class App(Streamer[AppSession]):
    """Miniappi application

    This class is the entrypoint
    to create apps and it handles
    the communication with Miniappi
    server.

    Args:
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
    cls_session = AppSession

    def __init__(self,
                 *,
                 user_context: Context | None = None,
                 app_context: Context | None = None):
        super().__init__(None)

        self.channel_context = user_context
        self.app_context = app_context

    def get_app_context_managers(self, args: dict):
        init_args = dict(
            app=self,
            sessions=self.sessions,
            **args
        )
        ctx = [
            *self.app_context_managers,
            default_app_context.enter(init_args),
        ]
        if self.app_context:
            ctx.append(self.app_context.enter())
        return ctx

    def _update_app_context(self, args: dict):
        # Update app context after recovery
        for key, val in args.items():
            setattr(default_app_context, key, val)

    def get_channel_context_managers(self, session: AppSession):
        init_args = dict(
            session=session,
            request_id=session.start_args.request_id,
        )
        ctx = [
            *self.channel_context_managers,
            default_channel_context.enter(
                init_args
            ),
        ]
        if self.channel_context:
            ctx.append(self.channel_context.enter())
        return ctx

    def get_logger(self, name: str):
        return logger
