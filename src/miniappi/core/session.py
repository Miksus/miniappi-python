import asyncio
import logging
from typing import List, Dict, Awaitable, Any, Callable
from collections.abc import Callable
from contextlib import asynccontextmanager, AsyncExitStack
from pydantic import BaseModel
from .exceptions import UserLeftException
from .connection import AbstractUserConnection, Message
from .connection import UserSessionArgs
from .models.message_types import InputMessage, PutRoot, BaseMessage
from .models.content import BaseContent

type RequestStreams = List[Callable[[dict], Awaitable[Any]]]

class Session:

    callbacks_message: RequestStreams
    tasks: List[asyncio.Task]

    def __init__(self, start_conn: AbstractUserConnection,
                 start_args: UserSessionArgs,
                 callbacks_message: RequestStreams,
                 sessions: Dict[str, "Session"]):
        self.start_conn = start_conn
        self.start_args = start_args

        self.callbacks_message = callbacks_message

        self._sessions = sessions
        self._sessions[start_args.request_id] = self

        self.tasks = []

        self.is_running = False

    @property
    def request_id(self):
        return self.start_args.request_id

    async def send(self, data: dict | BaseModel):
        "Send to the response channel"

        logger = self.get_logger()
        logger.info("Sending data")
        body = self._format_send_message(data)

        await self.start_conn.send(body)

    def _format_send_message(self, data):
        if isinstance(data, BaseContent):
            # Considering as put message
            data = PutRoot(
                data=data
            )
        if isinstance(data, dict):
            data = InputMessage(**data)
        if not isinstance(data, BaseMessage):
            raise TypeError(f"Expected: {BaseMessage!r}, given: {type(data)!r}")
        
        return data.model_dump(exclude_none=True)

    async def _publish(self, body):
        await self.start_conn.send(body)

    async def listen(self):
        "Listen the request channel"
        logger = self.get_logger()
        try:
            logger.info("Listening channel")
            self.is_running = True
            async for message in self.start_conn.listen():
                if message is not None:
                    await self._handle_request_message(message)
                await asyncio.sleep(0)
        finally:
            self.is_running = False

    async def close(self, send_stop=True):
        "Close listening and remove session"
        logger = self.get_logger()
        logger.debug("Closing channel")
        self._sessions.pop(self.start_args.request_id)
        for task in self.tasks:
            task.cancel()
        if send_stop:
            await self._send_stop()

    async def _handle_request_message(self, msg: Message):
        if self._is_stop_message(msg):
            raise UserLeftException("Client requested to close")
        for func in self.callbacks_message:
            await func(msg)

    def get_logger(self):
        return logging.getLogger(__name__)

    def _is_stop_message(self, message: Message):
        return message.data == "OFF"

    async def _send_stop(self):
        "Send stop message"
        await self._publish("OFF")
