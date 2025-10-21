from typing import Generic, TypeVar, AsyncGenerator, AsyncContextManager
from dataclasses import dataclass
from abc import ABC, abstractmethod
from pydantic import BaseModel


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
