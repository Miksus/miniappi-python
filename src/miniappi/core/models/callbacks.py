from typing import Any, Awaitable
from collections.abc import Callable
from pydantic import BaseModel
from miniappi.core.connection import Message

class StartArgs(BaseModel):
    request_id: str
    request_channel: str | None
    response_channel: str | None
    channel: str | None = None

class OnMessageConfig:

    def __init__(self, func: Callable[[Message], Awaitable[Any]]):
        self.func = func

    async def __call__(self, msg: Message):
        return await self.func(msg)

class OnOpenConfig:

    def __init__(self, func: Callable[[Message], Awaitable[Any]], pass_session):
        self.func = func
        self.pass_session = pass_session

    async def __call__(self, *args, **kwargs):
        return await self.func(*args, **kwargs)
