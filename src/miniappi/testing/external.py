import time
from datetime import timedelta
import asyncio
from typing import Callable, List, AsyncIterable
from contextlib import asynccontextmanager
from uuid import uuid4

from miniappi import app_context
from miniappi.core import App
from miniappi.core.connection import Message
from miniappi.core.connection.mock import MockClient, MockUserSessionArgs

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

    def __init__(self, stream: App, request_id: str):
        self.stream = stream
        self.request_id = request_id

        self.received = []
        self.sent = []

        self._n_sent = 0

        self.conn_client = self.stream.conn_client
        if not isinstance(self.stream.conn_client, MockClient):
            raise TypeError("Testing handler only works for MockClient")

    @property
    def start_args(self):
        return MockUserSessionArgs(
            request_id=self.request_id,
            channel=self.channel_name,
        )

    async def start_communication(self, timeout):
        await self.conn_client.add_session(
            app_name=self.stream.app_name,
            request_id=self.request_id
        )
        async with asyncio.timeout(timeout):
            while not self.is_running():
                await asyncio.sleep(0)

    def is_running(self):
        session = self.stream.sessions.get(self.request_id)
        if not session:
            return False
        return session.is_running

    def get_url(self):
        return self.conn_client._get_url(
            self.stream.app_name,
            self.request_id
        )

    async def wait_for_sent(self):
        req, resp = self.conn_client._get_queue(
            self.stream.app_name,
            self.request_id
        )
        if resp is None:
            return
        while not resp.empty():
            message_data = await resp.get()
            message = Message(
                url=self.stream.app_name,
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
                (self.stream.app_name, self.request_id)
            )
            if queue is not None:
                while not queue.empty():
                    message_data = await queue.get()
                    message = Message(
                        url=self.channel_name,
                        request_id=self.request_id,
                        data=message_data
                    )
                    self.sent.append(message)
                    return message
            await asyncio.sleep(0)

    async def send_message(self, msg: dict | str):
        "Send message to the streamer"
        await self.conn_client._add_request(
            app_name=self.stream.app_name,
            request_id=self.request_id,
            msg=msg
        )
        self._n_sent += 1

@asynccontextmanager
async def listen(stream: App, request_id: str = None, start_args: dict = None, wait_close=False):
    "Communicate with a stream"
    start_args = start_args or {}
    request_id = request_id or str(uuid4())
    timeout = 10

    handler = StreamHandler(
        stream=stream,
        request_id=request_id,
    )

    @stream.on_message()
    async def record_message(message: Message):
        if message.url == handler.get_url():
            handler.received.append(message)

    async with asyncio.timeout(timeout):
        while True:
            if stream.is_running:
                break
            await asyncio.sleep(0)

    await handler.start_communication(
        timeout=timeout
    )

    async with asyncio.timeout(timeout):
        yield handler

    async with asyncio.timeout(timeout):
        await handler.wait_for_messages()

    if wait_close:
        async with asyncio.timeout(timeout):
            while stream.is_running:
                await asyncio.sleep(0)
