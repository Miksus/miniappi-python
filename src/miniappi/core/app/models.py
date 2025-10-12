from typing import Union, TYPE_CHECKING, Generator
from uuid import uuid4
from contextlib import contextmanager
from pydantic import BaseModel
from .context import user_context, app_context

if TYPE_CHECKING:
    from .stream import AppSession

class BaseContent(BaseModel):
    id: str

    def __init__(self, id: str | None = None, *args, **kwargs):
        if id is None:
            id = str(uuid4())
        super().__init__(*args, id=id, **kwargs)

    async def show(self, session: Union["AppSession", None] = None):
        if session is not None:
            return await session.send(self)
        try:
            session = user_context.session
            await session.send(self)
        except LookupError:
            # Called outside of channel
            # --> set as root to all channels
            for session in app_context.sessions.values():
                await session.send(self)

    async def wait_input(self, show=True, *args, **kwargs):
        from miniappi.flow.interact import wait_for_input
        output = await wait_for_input(self, show=show, *args, **kwargs)
        return output

    def iter_content(self) -> Generator["BaseContent"]:

        def _iter_content(value):
            if isinstance(value, BaseContent):
                yield from value.iter_content()
            elif isinstance(value, (list, tuple, set)):
                for subval in value:
                    yield from _iter_content(subval)
            elif isinstance(value, dict):
                for subval in value.values():
                    yield from _iter_content(subval)

        yield self
        fields = type(self).model_fields
        for name, field in fields.items():
            value = getattr(self, name)
            yield from _iter_content(value)

class BaseMessage(BaseModel):
    ...
