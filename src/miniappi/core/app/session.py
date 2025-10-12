
from miniappi.core.stream.session import StreamSession
from .models import BaseMessage, BaseContent
from .message_types import InputMessage, PutRoot

from .context import user_context
from .utils.message import handle_message
import logging

logger = logging.getLogger(__name__)


class AppSession(StreamSession):

    def get_logger(self, name: str | None = None):
        return logger

    async def send(self, data):
        if isinstance(data, BaseContent):
            # Considering as put message
            data = PutRoot(
                data=data
            )
        if isinstance(data, dict):
            data = InputMessage(**data)
        if not isinstance(data, BaseMessage):
            raise TypeError(f"Expected: {BaseMessage!r}, given: {type(data)!r}")
        out = await super().send(data.model_dump(exclude_none=True))
        self._set_context(data)
        return out

    def _set_context(self, msg: InputMessage):
        ... # TODO
        #curr_content = channel_context.current_content
        # handle_message(curr_content, msg)
