from typing import Generic, TypeVar, AsyncGenerator, Literal, Self, AsyncContextManager
import json
import logging
from dataclasses import dataclass
from contextlib import asynccontextmanager
from abc import ABC, abstractmethod
from httpx_ws import aconnect_ws, AsyncWebSocketSession
from httpx import AsyncClient
from pydantic import BaseModel

from miniappi.config import settings
from .exceptions import CloseSessionException

ConnectionT = TypeVar("ConnectionT")
SessionT = TypeVar("SessionT")

class BaseStartArgs(BaseModel):
    request_id: str

@dataclass
class Message:
    channel: str
    request_id: str | None
    data: dict

class AbstractConnection(ABC):

    @abstractmethod
    async def publish(self, data: dict):
        "Publish a message to the connection"
        ...

    @abstractmethod
    async def listen(self) -> AsyncGenerator[Message]:
        "Listen messages from the connection"
        ...

    @abstractmethod
    async def listen_start(self) -> AsyncGenerator[BaseStartArgs]:
        "Listen start message from the connection"
        ...

class AbstractChannel(ABC, Generic[ConnectionT]):

    def __init__(self):
        self.app_url: str | None = None
        self.app_name: str | None = None

    @abstractmethod
    def connect(self) -> AsyncContextManager[ConnectionT]:
        ...

class AbstractClient(ABC, Generic[SessionT]):

    @abstractmethod
    def from_start_args(self, args) -> SessionT:
        "Init client from start args (for session)"

    @abstractmethod
    def from_init_channel(self, app_name: str) -> SessionT:
        "Init client from channel name (for app init)"
        ...

# Websocket

class WebsocketStartArgs(BaseStartArgs):
    channel: str = None

class WebsocketConnection(AbstractConnection):

    def __init__(self, ws: AsyncWebSocketSession, client: "WebsocketClient"):
        self.ws = ws
        self.client = client

    async def publish(self, data: dict):
        data = json.dumps(data)
        await self.ws.send_text(data)

    async def listen(self):
        while True:
            data = await self.ws.receive_text()
            if data == "OFF":
                # Users disconnected
                raise CloseSessionException("User closed the session")
            message = json.loads(data)
            yield Message(
                channel=self.client.channel,
                request_id=self.client.request_id,
                data=message
            )

    async def listen_start(self):
        async for msg in self.listen():
            yield WebsocketStartArgs(**msg.data)

class WebsocketChannel(AbstractChannel[WebsocketConnection]):

    def __init__(self, client: AsyncClient, channel: str, request_id: str | None, is_anonymous: bool = True):
        self.client = client
        self.channel = channel
        self.request_id = request_id
        self.is_anonymous = is_anonymous

        self.app_url: str | None = None
        self.app_name: str | None = None
        super().__init__()

    @asynccontextmanager
    async def connect(self):
        logger = logging.getLogger(__name__)
        logger.info(f"Connecting: {self.channel}")
        async with aconnect_ws(self.channel, client=self.client, keepalive_ping_interval_seconds=settings.timeout, keepalive_ping_timeout_seconds=settings.timeout) as ws:
            is_start = self.request_id is None
            if is_start:
                is_anonymous = self.is_anonymous
                if is_anonymous:
                    # The start sends a payload for
                    # generated UUID
                    # We show this UUID to the user
                    # so they can go to the app page
                    uuid = await ws.receive_json()
                    self.app_name = uuid
                    self.app_url = f"{settings.url_apps}/{uuid}"
                else:
                    self.app_url = f"{settings.url_apps}/{self.app_name}"
            yield WebsocketConnection(ws, client=self)


class WebsocketClient(AbstractClient[WebsocketChannel]):

    def __init__(self, client: AsyncClient | None = None):
        self.client = client or AsyncClient(timeout=settings.timeout)

    def from_start_args(self, args: WebsocketStartArgs) -> WebsocketChannel:
        return WebsocketChannel(
            client=self.client,
            channel=args.channel,
            request_id=args.request_id,
        )

    def from_init_channel(self, app_name: str | None) -> WebsocketChannel:
        is_anonymous = app_name is None
        url = (
            settings.url_start
            if is_anonymous
            else f"{settings.url_start}/{app_name}"
        )
        return WebsocketChannel(
            client=self.client,
            channel=url,
            request_id=None,
            is_anonymous=is_anonymous
        )
