from contextlib import asynccontextmanager
import json
import logging
import asyncio
from typing import Callable, Any
from dataclasses import dataclass, asdict
from pydantic import BaseModel
from httpx_ws import aconnect_ws, AsyncWebSocketSession, WebSocketNetworkError, WebSocketDisconnect
from httpx import AsyncClient

from rich import print
from rich.panel import Panel

from miniappi.core.exceptions import CloseSessionException
from .base import (
    AbstractUserConnection,
    AbstractClient,
    ServerConf,
    ClientConf,
    UserSessionArgs,
    Message
)
from miniappi.config import settings

@dataclass(kw_only=True)
class WebsocketUserSessionArgs(UserSessionArgs):
    user_url: str

@dataclass
class RecoveryConf:
    recovery_key: str

async def _listen_messages(ws: AsyncWebSocketSession):
    while True:
        data = await ws.receive_text()
        if data.lower() == "off":
            # Users disconnected
            raise CloseSessionException("User closed the session")
        elif data.lower() == "ping":
            continue
        message = json.loads(data)
        yield message
        await asyncio.sleep(0)

class WebsocketUserConnection(AbstractUserConnection):

    def __init__(self, ws: AsyncWebSocketSession, start_args: WebsocketUserSessionArgs):
        self.ws = ws
        self.start_args = start_args

    async def send(self, data: dict):
        "Send a message to a user"
        await self.ws.send_json(data)

    async def listen(self):
        "Listen messages from the user"
        try:
            async for msg in _listen_messages(self.ws):
                yield Message(
                    url=self.start_args.user_url,
                    request_id=self.start_args.request_id,
                    data=msg
                )
        except WebSocketDisconnect as exc:
            if exc.code == 1000:
                raise CloseSessionException(exc.reason)
            raise

class WebsocketClient(AbstractClient):

    def __init__(self, client: AsyncClient | None = None):
        self.client = client or AsyncClient(timeout=settings.timeout)

    @asynccontextmanager
    async def connect_user(self, start_args: WebsocketUserSessionArgs):
        async with aconnect_ws(
            start_args.user_url,
            client=self.client,
            keepalive_ping_interval_seconds=settings.keepalive_ping_interval,
            keepalive_ping_timeout_seconds=settings.keepalive_ping_timeout
        ) as ws:
            yield WebsocketUserConnection(ws, start_args)

    async def listen_app(self, conf: ClientConf, setup_start: Callable[[ServerConf, ...], Any]):
        url = (
            settings.url_start
            if conf.app_name is None
            else f"{settings.url_start}/{conf.app_name}"
        )
        n_fails = 0
        recovery_key = None
        while True:
            is_reconnect = False
            try:
                async with aconnect_ws(
                    url,
                    client=self.client,
                    keepalive_ping_interval_seconds=settings.keepalive_ping_interval,
                    keepalive_ping_timeout_seconds=settings.keepalive_ping_timeout
                ) as ws:
                    n_fails = 0
                    if not is_reconnect:
                        # Initialize the app
                        await ws.send_json(asdict(conf))
                        server_conf = ServerConf(**await ws.receive_json())
                        await setup_start(
                            server_conf
                        )
                    recovery_conf = RecoveryConf(await ws.receive_json())
                    recovery_key = recovery_conf.recovery_key
                    async for msg in _listen_messages(ws):
                        yield WebsocketUserSessionArgs(**msg)
            except WebSocketNetworkError as exc:
                # Reconnecting...
                if recovery_key:
                    is_reconnect = True
                    url = f"{settings.url_recover}/{recovery_key}"
                else:
                    # Didn't yet even initialize
                    is_reconnect = False

                # Wait for 0, 1, 8, 27, 64 ...
                # after each fail in row

                reconnect_delay = n_fails ** 3
                n_fails += 1
                if reconnect_delay > (60 * 60):
                    # Too many fails, the server timeouts
                    # before the wait
                    raise
                
                await asyncio.sleep(reconnect_delay)
            except WebSocketDisconnect as exc:
                if exc.code == 1000:
                    # Normal closure
                    raise CloseSessionException(exc.reason)
                raise
