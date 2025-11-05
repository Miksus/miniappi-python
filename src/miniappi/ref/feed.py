import asyncio
from uuid import uuid4
from pydantic import Field
from typing import Generic, TypeVar, Literal, List
from collections import UserList, defaultdict
from miniappi.core import user_context, app_context, Session
from miniappi.core.models.message_types import PushRight, PutRef
from miniappi.core.models.references import ArrayReference

T = TypeVar("T")

class Feed(ArrayReference, Generic[T]):

    def __init__(self, data: List[T] | None = None,
                 *,
                 limit: int = 20,
                 method: Literal['lifo', 'fifo', 'ignore'] = "fifo",
                 id: str | None = None):
        super().__init__(
            data=data or [],
            limit=limit,
            method=method,
            reference=id or str(uuid4()),
        )
        self._trim()

    def _trim(self):
        if len(self.data) > self.limit:
            if self.method == "fifo":
                self.data = self.data[-self.limit:]
            if self.method == "lifo":
                self.data = self.data[:self.limit]

    async def append(self, element: T):
        """Append to the feed and show it to the user
        (if user context) or all (if no user context)"""

        self.data.append(element)
        self._trim()
        try:
            await self._push_session(element, user_context.session)
        except LookupError:
            for session in app_context.sessions.values():
                await self._push_session(element, session)

    async def _push_session(self, elem, session: Session):
        await session.send(
            PushRight(
                id=self.reference,
                data=elem
            )
        )
