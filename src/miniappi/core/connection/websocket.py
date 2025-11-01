from contextlib import asynccontextmanager
import json
import logging
import asyncio
from anyio import EndOfStream
from typing import Callable, Any
from dataclasses import dataclass, asdict
from httpx_ws import aconnect_ws, AsyncWebSocketSession, WebSocketNetworkError, WebSocketDisconnect, WebSocketUpgradeError
from httpx import AsyncClient
import httpcore

from miniappi.core.logging import Loggers

from miniappi.core.exceptions import UserLeftException
from .base import (
    AbstractUserConnection,
    AbstractClient,
    ServerConf,
    ClientConf,
    UserSessionArgs,
    Message
)
from miniappi.config import settings

LOGGER = logging.getLogger(Loggers.connection.value)
LOGGER_USER = logging.getLogger(Loggers.user_connection.value)
LOGGER_APP = logging.getLogger(Loggers.app_connection.value)

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
            LOGGER.debug("Received a close message")
            raise UserLeftException("Server closed the session")
        elif data.lower() == "ping":
            LOGGER.debug("Received a ping message")
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
        LOGGER_USER.info("Message sent")

    async def listen(self):
        "Listen messages from the user"
        try:
            async for msg in _listen_messages(self.ws):
                LOGGER_USER.info("Message received")
                yield Message(
                    url=self.start_args.user_url,
                    request_id=self.start_args.request_id,
                    data=msg
                )
        except WebSocketDisconnect as exc:
            if exc.code in (1000, 1001):
                if exc.code == 1001:
                    LOGGER_USER.info("User left")
                else:
                    LOGGER_USER.info("User session closed by server")
                raise UserLeftException(exc.reason)
            LOGGER_USER.exception("Server disconnected")
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
            ...
        ...

    async def listen_app(self, conf: ClientConf, setup_start: Callable[[ServerConf, ...], Any]):
        url = (
            settings.url_start
            if conf.app_name is None
            else f"{settings.url_start}/{conf.app_name}"
        )
        n_fails = 0
        recovery_key = None
        is_reconnect = False
        while True:
            try:
                if is_reconnect:
                    LOGGER_APP.info("Reconnecting to app...")
                else:
                    LOGGER_APP.info("Connecting to app...")
                async with aconnect_ws(
                    url,
                    client=self.client,
                    keepalive_ping_interval_seconds=settings.keepalive_ping_interval,
                    keepalive_ping_timeout_seconds=settings.keepalive_ping_timeout
                ) as ws:
                    if not is_reconnect:
                        # Initialize the app
                        await ws.send_json(asdict(conf))
                        server_conf = ServerConf(**await ws.receive_json())
                        await setup_start(
                            server_conf
                        )
                    recovery_conf = RecoveryConf(**await ws.receive_json())
                    recovery_key = recovery_conf.recovery_key
                    LOGGER_APP.info("App connected")
                    n_fails = 0
                    async for msg in _listen_messages(ws):
                        LOGGER_APP.info("User joined")
                        yield WebsocketUserSessionArgs(**msg)
            except (WebSocketNetworkError, WebSocketDisconnect, ExceptionGroup, WebSocketUpgradeError) as exc:
                # Reconnecting...

                if isinstance(exc, ExceptionGroup):
                    # anyio may leak EndOfStream to httpcore and to http-ws
                    # in http-ws background task. This possibly is caused
                    # by keepalive pinging
                    # See: https://github.com/encode/httpcore/discussions/1045
                    all_stream_related = all(
                        isinstance(e, (EndOfStream, httpcore.NetworkError, httpcore.TimeoutException))
                        for e in exc.exceptions
                    )
                    if not all_stream_related:
                        raise

                if isinstance(exc, WebSocketDisconnect) and exc.code == 1000:
                    # Normal closure, don't reconnect
                    raise

                if recovery_key:
                    is_reconnect = True
                    url = f"{settings.url_recover}/{recovery_key}"
                else:
                    # Didn't yet even initialize
                    is_reconnect = False

                # Wait for 0, 1, 8, 27, 64 ...
                # after each fail in row

                reconnect_delay = (n_fails + 1) ** 3
                n_fails += 1
                if reconnect_delay > (60 * 60):
                    # Too many fails, the server timeouts
                    # before the wait
                    LOGGER_APP.exception(
                        "Network interupted. Could not reconnect"
                    )
                    raise
                
                # Log the error
                msg = (
                    f"Connection interupted with code {exc.code} ({exc.reason!r}). "
                    if isinstance(exc, WebSocketDisconnect)
                    else f"Network interupted. "
                    if isinstance(exc, WebSocketNetworkError)
                    else f"Stream crashed with error {exc!r}. "
                )
                LOGGER_APP.warning(
                    msg + f"Reconnecting in {reconnect_delay}..."
                )
                await asyncio.sleep(reconnect_delay)
            except WebSocketDisconnect as exc:
                if exc.code in (1001, 1000):
                    # Normal closure
                    LOGGER_APP.info("Server closed")
                    raise UserLeftException(exc.reason)
                LOGGER_APP.exception("Server disconnected")
                raise
