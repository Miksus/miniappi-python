import asyncio
from uuid import uuid4
from typing import Dict, List, Tuple, AsyncGenerator, AsyncIterator, AsyncContextManager, Callable, Any
from collections import defaultdict
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager
from abc import ABC, abstractmethod
from .base import (
    AbstractClient, AbstractUserConnection,
    ClientConf, ServerConf,
    Message, UserSessionArgs
)

from miniappi.config import settings

@dataclass(kw_only=True)
class MockUserSessionArgs(UserSessionArgs):
    user_url: str

class MockUserConnection(AbstractUserConnection):

    def __init__(self, client: "MockClient", start_args: MockUserSessionArgs):
        self._client = client
        self._start_args = start_args

    async def send(self, data: dict):
        "Send a message to a user"
        url = self._start_args.user_url
        await self._client.response_queue[
            url
        ].put(
            data
        )

    async def listen(self) -> AsyncGenerator[Message]:
        "Listen messages from the user"
        request_id = self._start_args.request_id
        url = self._start_args.user_url
        while True:
            queue = self._client.request_queue
            this_queue = queue.get(
                url
            )
            if this_queue is not None:
                next_msg = await this_queue.get()
                msg = Message(
                    url=url,
                    request_id=request_id,
                    data=next_msg
                )
                self._client.received.append(msg)
                yield msg
            await asyncio.sleep(0)

class MockClient(AbstractClient):

    def __init__(self):
        self.session_queue: Dict[str, asyncio.Queue[Message]] = defaultdict(asyncio.Queue)
        self.request_queue: Dict[str, asyncio.Queue[Message]] = defaultdict(asyncio.Queue)
        self.response_queue: Dict[str, asyncio.Queue[Message]] = defaultdict(asyncio.Queue)

        self.sent: List[Message] = []
        self.received: List[Message] = []

        # Triggers for testing
        self.network_error_on_start = False

        # Mocks need
        self._app_name = None

    @asynccontextmanager
    async def connect_user(self, args: MockUserSessionArgs):
        "Connect with a user"
        yield MockUserConnection(self, start_args=args)

    async def listen_app(self, config: ClientConf, setup_start: Callable[[ServerConf, ...], Any]) -> AsyncIterator[Message]:
        "Connect the app and listen session starts"
        app_name = str(uuid4())
        app_url = f"{settings.url_apps}/{app_name}"
        await setup_start(
            ServerConf(
                app_name=app_name,
                app_url=app_url
            )
        )

        while True:
            queue = self.session_queue
            this_queue = queue.get(self._get_url(app_name))
            if this_queue is not None:
                next_msg = await this_queue.get()

                self.received.append(next_msg)
                yield MockUserSessionArgs(**next_msg)
            await asyncio.sleep(0)

    async def add_session(self, app_name: str, request_id: str):
        "Simulate other side of the stream"
        await self.session_queue[self._get_url(app_name)].put(
            asdict(
                MockUserSessionArgs(
                    request_id=request_id,
                    user_url=self._get_url(app_name, request_id)
                )
            )
        )

    async def _add_request(self, app_name: str, request_id: str, msg: str | dict):
        await self.request_queue[self._get_url(app_name, request_id)].put(
            msg
        )

    def _get_url(self, app_name: str, request_id: str | None = None):
        if request_id is not None:
            return f"{settings.url_start}/{app_name}/{request_id}"
        else:
            return f"{settings.url_start}/{app_name}/{request_id}"

    def _get_queue(self, app_name: str, request_id: str) -> Tuple[asyncio.Queue, asyncio.Queue]:
        url = self._get_url(app_name, request_id)
        return (
            self.request_queue.get(url),
            self.response_queue.get(url),
        )
