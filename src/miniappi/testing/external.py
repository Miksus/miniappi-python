import time
from datetime import timedelta
import asyncio
from typing import Callable, List, AsyncIterable
from contextlib import asynccontextmanager
from uuid import uuid4

from miniappi.core.stream import Streamer
from miniappi.core.stream.connection import Message
from .mock import MockClient, MockStartArgs

async def _wait_for_condition(cond: Callable, sleep=0, timeout: int=5):
    start = time.time()
    while not cond():
        if (time.time() - start) > timeout:
            raise TimeoutError(cond)
        await asyncio.sleep(sleep)

class StreamHandler:

    conn_client: MockClient
    received: List[Message]
    sent: List[Message]

    def __init__(self, stream: Streamer, request_id: str):
        self.stream = stream
        self.request_id = request_id

        self.received = []
        self.sent = []

        self._n_sent = 0
        self._channel_name = stream.url

        self.conn_client = self.stream.conn_client
        if not isinstance(self.stream.conn_client, MockClient):
            raise TypeError("Testing handler only works for MockClient")

    @property
    def channel_name(self):
        if self._channel_name is None:
            self._channel_name = str(uuid4())
        return self._channel_name

    @property
    def start_args(self):
        return MockStartArgs(
            request_id=self.request_id,
            channel=self.channel_name,
        )

    async def start_communication(self, **kwargs):
        await self.conn_client.request_queue[(self.stream.url, None)].put(
            self.start_args.model_dump()
        )

    def is_subscribed(self):
        session = self.stream.sessions.get(self.request_id)
        if not session:
            return False
        return session.subscribed

    async def wait_for_stream_ready(self, timeout=1):
        async with asyncio.timeout(timeout):
            while not self.is_subscribed():
                await asyncio.sleep(0)

    async def wait_for_sent(self):
        queue = self.conn_client.response_queue.get(
            (self.channel_name, self.request_id)
        )
        if queue is None:
            return
        while not queue.empty():
            message_data = await queue.get()
            message = Message(
                channel=self.channel_name,
                request_id=self.request_id,
                data=message_data
            )
            self.sent.append(message)
            await asyncio.sleep(0)

    async def wait_for_received(self):
        while self._n_sent != len(self.received):
            await asyncio.sleep(0)

    async def wait_for_messages(self):
        await self.wait_for_received()
        await self.wait_for_sent()

    async def get_next_sent(self):
        "Get next sent message"
        while True:
            queue = self.conn_client.response_queue.get(
                (self.channel_name, self.request_id)
            )
            if queue is not None:
                while not queue.empty():
                    message_data = await queue.get()
                    message = Message(
                        channel=self.channel_name,
                        request_id=self.request_id,
                        data=message_data
                    )
                    self.sent.append(message)
                    return message
            await asyncio.sleep(0)

    async def send_message(self, msg: dict | str):
        "Send message to the streamer"
        queue = self.conn_client.request_queue[(self.channel_name, self.request_id)]
        await queue.put(
            msg
        )
        self._n_sent += 1

@asynccontextmanager
async def listen(stream: Streamer, request_id: str = None, start_args: dict = None, wait_close=False):
    "Communicate with a stream"
    start_args = start_args or {}
    request_id = request_id or str(uuid4())

    handler = StreamHandler(
        stream=stream,
        request_id=request_id,
    )

    @stream.on_message()
    async def record_message(message: Message):
        if message.channel == handler.channel_name and message.request_id == handler.request_id:
            handler.received.append(message)

    async with asyncio.timeout(2):
        while True:
            if stream.subscribed:
                break
            await asyncio.sleep(0)

    async with asyncio.timeout(2):
        await handler.start_communication(
            **start_args
        )
        await handler.wait_for_stream_ready()

    async with asyncio.timeout(2):
        yield handler

    async with asyncio.timeout(2):
        await handler.wait_for_messages()

    if wait_close:
        async with asyncio.timeout(2):
            while stream.subscribed:
                await asyncio.sleep(0)
