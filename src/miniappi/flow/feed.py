import asyncio
from typing import Generic, TypeVar, Literal
from collections import UserList
from miniappi.core.app import BaseContent, user_context, app_context, PushRight, PutRef, AppSession
from miniappi.core.stream.connection import Message

T = TypeVar("T")

class Feed(UserList, Generic[T]):
    """Content Feed"""

    def __init__(self, initlist=None, id=None, scope: Literal["app", "user", "auto"] = None):
        super().__init__(initlist)
        self.id = id
        self.scope = scope

    async def _push_session(self, elem, session: AppSession):
        await session.send(
            PushRight(
                id=self.id,
                data=elem
            )
        )

    async def show(self, session: AppSession | None = None):
        "Send all items in the feed to the session"
        msg = PutRef(
            id=self.id,
            data=self.data
        )
        if session is not None:
            return await session.send(msg)
        try:
            session = user_context.session
            await session.send(msg)
        except LookupError:
            # Called outside of channel
            # --> set as root to all channels
            for session in app_context.sessions.values():
                await session.send(msg)

    async def append_all(self, element: T):
        "Append to the feed and show it to all"
        self.data.append(element)
        for session in app_context.sessions.values():
            await self._push_session(element, session)

    async def append(self, element: T):
        """Append to the feed and show it to the user
        (if user context) or all (if no user context)"""
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
