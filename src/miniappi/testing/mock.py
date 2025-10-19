import asyncio
from typing import List, Dict, Tuple
from uuid import uuid4
from collections import defaultdict
from dataclasses import asdict
from contextlib import asynccontextmanager
from miniappi.core.stream.connection import (
    BaseStartArgs,
    AbstractConnection,
    AbstractChannel,
    AbstractClient, Message,
    ServerConf, ClientConf
)
from httpx_ws import WebSocketNetworkError

class MockStartArgs(BaseStartArgs):
    channel: str | None

class MockConnection(AbstractConnection):

    def __init__(self, channel: "MockChannel"):
        self.channel = channel

    async def publish(self, data: str):
        await self._store.response_queue[
            (self.channel.channel_name, self.channel.request_id)
        ].put(
            data
        )

    async def listen(self):
        while True:
            queue = self._store.request_queue
            this_queue = queue.get(
                (self.channel.channel_name, self.channel.request_id)
            )
            if this_queue is not None:
                next_msg = await this_queue.get()
                msg = Message(
                    channel=self.channel.channel_name,
                    request_id=self.channel.request_id,
                    data=next_msg
                )
                self._store.received.append(msg)
                yield msg
            await asyncio.sleep(0)

    async def init_app(self, conf: ClientConf):
        self._client_conf = conf
        app_name = self.channel.channel_name
        return ServerConf(
            app_url=f"http://localhost:0000/apps/{app_name}",
            app_name=app_name,
            recovery_key=str(uuid4())
        )

    async def listen_start(self):

        async for msg in self.listen():
            if self._store.network_error_on_start:
                raise WebSocketNetworkError("Not connected")
            yield MockStartArgs(**msg.data)

    @property
    def _store(self):
        return self.channel.store

class MockChannel(AbstractChannel[MockConnection]):

    def __init__(self, channel: str, request_id: str | None, store: "MockClient"):
        super().__init__()
        self.channel_name = channel
        self.request_id = request_id
        self.store = store

    @asynccontextmanager
    async def connect(self):
        yield MockConnection(channel=self)

class MockClient(AbstractClient[MockChannel]):

    def __init__(self):
        self.request_queue: Dict[Tuple[str, str], asyncio.Queue[dict]] = defaultdict(asyncio.Queue)
        self.response_queue: Dict[Tuple[str, str], asyncio.Queue[dict]] = defaultdict(asyncio.Queue)

        self.sent: List[Message] = []
        self.received: List[Message] = []
        super().__init__()

        # Triggers for testing
        self.network_error_on_start = False

        # Mocks need
        self._app_name = None

    def from_start_args(self, args: MockStartArgs):
        return MockChannel(
            channel=args.channel,
            request_id=args.request_id,
            store=self
        )

    def from_init_channel(self, app_name: str | None):
        app_name = app_name or str(uuid4())
        self._app_name = app_name
        return MockChannel(
            channel=app_name,
            request_id=None,
            store=self
        )

    def from_reconnect(self, app_name: str, recovery_key: str):
        return MockChannel(
            channel=app_name,
            request_id=None,
            store=self
        )
