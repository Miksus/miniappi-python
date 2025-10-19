from typing import Generic, TypeVar, AsyncGenerator, Literal, Self, AsyncContextManager
import json
import logging
from dataclasses import dataclass, asdict
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

@dataclass
class ServerConf:
    "Config given by Miniappi server"
    app_name: str
    app_url: str
    recovery_key: str | None = None

@dataclass
class ClientConf:
    "Config given by Miniappi client"
    version: str # Version of 

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

    @abstractmethod
    async def init_app(self, conf: dict) -> AsyncGenerator[ServerConf]:
        "Communicate app initiation"
        ...

class AbstractChannel(ABC, Generic[ConnectionT]):

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

    @abstractmethod
    def from_reconnect(self, app_name, recovery_key: str):
        "Init client from recovery"
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
            if data.lower() == "off":
                # Users disconnected
                raise CloseSessionException("User closed the session")
            elif data.lower() == "ping":
                continue
            message = json.loads(data)
            yield Message(
                channel=self.client.channel,
                request_id=self.client.request_id,
                data=message
            )

    async def init_app(self, conf: ClientConf):
        await self.ws.send_json(asdict(conf))
        confdata = await self.ws.receive_json()
        return ServerConf(**confdata)

    async def listen_start(self):
        async for msg in self.listen():
            yield WebsocketStartArgs(**msg.data)

class WebsocketChannel(AbstractChannel[WebsocketConnection]):

    def __init__(self, client: AsyncClient, channel: str, request_id: str | None):
        self.client = client
        self.channel = channel
        self.request_id = request_id
        super().__init__()

    @asynccontextmanager
    async def connect(self):
        logger = logging.getLogger(__name__)
        logger.info(f"Connecting: {self.channel}")
        async with aconnect_ws(self.channel, client=self.client, keepalive_ping_interval_seconds=settings.keepalive_ping_interval, keepalive_ping_timeout_seconds=settings.keepalive_ping_timeout) as ws:
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
        )

    def from_reconnect(self, app_name: str, recovery_key: str):
        return WebsocketChannel(
            client=self.client,
            channel=f"{settings.url_recover}/{app_name}/{recovery_key}",
            request_id=None,
        )
