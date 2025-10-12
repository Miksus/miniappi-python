import asyncio
from typing import Generic, TypeVar
from collections import UserList
from miniappi.core.app import BaseContent, user_context, app_context, PushRight, AppSession
from miniappi.core.stream.connection import Message

T = TypeVar("T")

class Feed(UserList, Generic[T]):

    def __init__(self, initlist=None, id=None):
        super().__init__(initlist)
        self.id = id

    async def _push_session(self, elem, session: AppSession):
        await session.send(
            PushRight(
                id=self.id,
                data=elem
            )
        )

    async def append_all(self, element: T):
        self.data.append(element)
        for session in app_context.sessions.values():
            await self._push_session(element, session)

    async def append(self, element: T):
        self.data.append(element)
        try:
            await self._push_session(element, user_context.session)
        except LookupError:
            for session in app_context.sessions.values():
                await self._push_session(element, session)

    def as_reference(self):
        return {
            "reference": self.id,
            "data": self.data
        }
