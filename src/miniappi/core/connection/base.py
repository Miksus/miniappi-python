from typing import Generic, TypeVar, AsyncGenerator, Callable, Self, AsyncContextManager, AsyncIterator, Any
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager
from abc import ABC, abstractmethod
from pydantic import BaseModel

from miniappi.config import settings

ConnectionT = TypeVar("ConnectionT")
SessionT = TypeVar("SessionT")

@dataclass(kw_only=True)
class UserSessionArgs:
    request_id: str

@dataclass
class Message:
    url: str
    request_id: str | None
    data: dict

@dataclass
class ServerConf:
    "Config given by Miniappi server"
    app_name: str
    app_url: str

@dataclass
class ClientConf:
    "Config given by Miniappi client"
    app_name: str | None
    version: str # Miniappi version

class AbstractUserConnection(ABC):

    @abstractmethod
    async def send(self, data: dict):
        "Send a message to a user"
        ...

    @abstractmethod
    async def listen(self) -> AsyncGenerator[Message]:
        "Listen messages from the user"
        ...

class AbstractClient(ABC):

    @abstractmethod
    async def connect_user(self, args) -> AsyncContextManager[AbstractUserConnection]:
        "Connect with a user"
        ...

    @abstractmethod
    async def listen_app(self, config: ClientConf, setup_start: Callable[[ServerConf, ...], Any]) -> AsyncIterator[Message]:
        "Connect the app and listen session starts"
        ...
