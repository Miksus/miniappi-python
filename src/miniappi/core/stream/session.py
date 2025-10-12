import asyncio
import logging
from typing import List, Dict, Awaitable, Any, Callable
from collections.abc import Callable
from contextlib import asynccontextmanager, AsyncExitStack
from pydantic import BaseModel
from .exceptions import CloseSessionException
from .connection import AbstractConnection, BaseStartArgs, Message

type RequestStreams = List[Callable[[dict], Awaitable[Any]]]

class StreamSession:

    callbacks_message: RequestStreams
    tasks: List[asyncio.Task]

    def __init__(self, start_conn: AbstractConnection,
                 start_args: BaseStartArgs,
                 callbacks_message: RequestStreams,
                 sessions: Dict[str, "StreamSession"]):
        self.start_conn = start_conn
        self.start_args = start_args

        self.callbacks_message = callbacks_message
        self._sessions = sessions

        self._pubsub = None

        self._sessions[start_args.request_id] = self
        self.tasks = []

        self.subscribed = False

    @property
    def request_id(self):
        return self.start_args.request_id

    async def send(self, data: dict | BaseModel):
        "Send to the response channel"

        logger = self.get_logger()
        logger.info("Sending data")
        await self._publish(data)

    @asynccontextmanager
    async def _subscribe(self):
        client = self.start_conn.from_start_args(self.start_args)
        async with client.connect() as connection:
            yield connection

    async def _listen(self):
        async for msg in self.start_conn.listen():
            yield msg

    async def _publish(self, body):
        await self.start_conn.publish(body)

    @asynccontextmanager
    async def _start(self):
        async with self._subscribe() as ws:
            self._pubsub = ws
            yield
            self._pubsub = None

    async def listen(self):
        "Listen the request channel"
        logger = self.get_logger()
        try:
            logger.info("Listening channel")
            self.subscribed = True
            async for message in self._listen():
                if message is not None:
                    await self._handle_request_message(message)
                await asyncio.sleep(0)
        finally:
            self.subscribed = False

    async def close(self, send_stop=True):
        "Close listening and remove session"
        logger = self.get_logger()
        logger.debug("Closing channel")
        #await self._pubsub.unsubscribe()
        self._sessions.pop(self.start_args.request_id)
        for task in self.tasks:
            task.cancel()
        if send_stop:
            await self._send_stop()

    async def _handle_request_message(self, msg: Message):
        if self._is_stop_message(msg):
            raise CloseSessionException("Client requested to close")
        for func in self.callbacks_message:
            await func(msg)

    def get_logger(self):
        return logging.getLogger(__name__)

    def _is_stop_message(self, message: Message):
        return message.data == "OFF"

    async def _send_stop(self):
        "Send stop message"
        await self._publish("OFF")
