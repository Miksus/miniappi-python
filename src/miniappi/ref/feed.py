import asyncio
from uuid import uuid4
import weakref
from pydantic import Field, PrivateAttr
from typing import Generic, TypeVar, Literal, List
from collections import UserList, defaultdict
from miniappi.core import user_context, app_context, Session
from miniappi.core.models.message_types import PushRight, PutRef
from miniappi.core.models.references import ArrayReference

T = TypeVar("T")

class Feed(ArrayReference, Generic[T]):
    """Feed of content or data

    Useful for stream of content or other
    data for the user. Appending to the feed
    triggers a push which sends only the
    new value to the user reducing the amount
    of data passed and making the app more
    responsive.

    Args:
        data (list, optional):
            Initial data to the feed.
            Empty list if not set.
        limit (int, optional): 
            Number of element in the list
            at maximum. Items are discarded
            according to the method policy
            if limit reached. Avoid setting this
            too high or you risk disconnection
            due to payload too big. By
            default 20.
        method ('fifo', 'lifo'):
            Whether items are removed first in,
            first out (fifo) or last in, first out
            (lifo). If fifo, items at the start of the
            list are removed first. If lifo, items at
            the end of the list removed first.
            By default 'fifo'.
        scope ('app', 'user', 'auto'):
            Whether a change triggers an event to
            all user sessions ('app'), only for
            the user in which the feed was created
            in ('user') or depending on the context
            ('auto'). By default auto.
        id (str, optional):
            Reference ID. By default, unique identifier.

    Examples:
        ```python
        from miniappi.ref import Feed

        @app.on_open()
        async def new_user(session):
            feed = Feed[str]()

            row = content.v0.layouts.Row(
                contents=feed
            )
            await row.show()
            await feed.append("a value")

        app.run()
        ```
    """
    scope: Literal["app", "user", "auto"] = Field(
        exclude=True
    )
    _scoped_session: Session | None = PrivateAttr(
        None,
    )

    def __init__(self, data: List[T] | None = None,
                 *,
                 limit: int = 20,
                 method: Literal['lifo', 'fifo', 'ignore'] = "fifo",
                 scope: Literal["app", "user", "auto"] = "auto",
                 id: str | None = None):
        super().__init__(
            data=data or [],
            limit=limit,
            method=method,
            scope=scope,
            reference=id or str(uuid4()),
        )
        self._trim()

        if self.scope == "user":
            self._scoped_session = weakref.ref(user_context.session)

    def _trim(self):
        if len(self.data) > self.limit:
            if self.method == "fifo":
                self.data = self.data[-self.limit:]
            if self.method == "lifo":
                self.data = self.data[:self.limit]

    async def append(self, element: T, session: Session | None = None):
        """Append to the feed and show it to the user
        (if user context) or all (if no user context)"""

        self.data.append(element)
        self._trim()

        if session is not None:
            return await self._push_session(element, session)
        if self.scope == "app":
            await self._push_all(element)
        elif self.scope == "user":
            return await self._push_session(element, self._scoped_session())
        elif self.scope == "auto":
            try:
                await self._push_session(element, user_context.session)
            except LookupError:
                await self._push_all(element)
        else:
            raise ValueError(f"Unknown scope: {self.scope}")

    async def _push_all(self, element: T):
        for session in app_context.sessions.values():
            await self._push_session(element, session)

    async def _push_session(self, elem: T, session: Session):
        await session.send(
            PushRight(
                id=self.reference,
                data=elem
            )
        )
