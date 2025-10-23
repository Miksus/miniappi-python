import asyncio
from uuid import uuid4
import urllib.parse
from dataclasses import asdict
from miniappi.core.connection.websocket import (
    WebsocketUserConnection,
    WebsocketClient
)
from contextlib import ExitStack, asynccontextmanager
import pytest
import httpx
from httpx_ws.transport import ASGIWebSocketTransport
from miniappi import App, app_context, settings
from miniappi.core.connection.websocket import WebsocketUserSessionArgs, ServerConf, RecoveryConf

from starlette.websockets import WebSocket
from starlette.applications import Starlette
from starlette.responses import HTMLResponse
from starlette.routing import Route, WebSocketRoute

def create_webapp(close_event: asyncio.Event):
    app_name = str(uuid4())
    request_id = "1234"
    async def endpoint_start_app(websocket: WebSocket):
        await websocket.accept()
        initdata = await websocket.receive_json()

        # Init
        await websocket.send_json(asdict(
            ServerConf(
                app_name=app_name,
                app_url=f"{settings.url_apps}/{app_name}"
            )
        ))

        # recovery
        recovery_key = str(uuid4())
        await websocket.send_json(asdict(
            RecoveryConf(
                recovery_key=recovery_key
            )
        ))

        # Sessions
        await websocket.send_json(asdict(
            WebsocketUserSessionArgs(
                request_id="1234",
                user_url=f"/v1/streams/apps/sessions/{app_name}/{request_id}"
            )
        ))

        #await close_event.wait()
        #await websocket.close()

    async def endpoint_start_session(websocket: WebSocket):
        await websocket.accept()

    start_path = urllib.parse.urlparse(settings.url_start).path
    return Starlette(
        routes=[
            WebSocketRoute(f"/v1/streams/apps/sessions/{app_name}/{request_id}", endpoint_start_session),
            WebSocketRoute(start_path, endpoint_start_app),
        ],
    )

@asynccontextmanager
async def create_web_client():
    close_event = asyncio.Event()
    webapp = create_webapp(close_event)
    async with httpx.AsyncClient(transport=ASGIWebSocketTransport(webapp), headers={'host': 'example.org'}) as client:
        yield client
        close_event.set()

@pytest.fixture
async def fake_ws_client():
    webapp = create_webapp()
    try:
        async with httpx.AsyncClient(transport=ASGIWebSocketTransport(webapp), headers={'host': 'example.org'}) as client:
            yield client
    except RuntimeError as exc:
        if exc.args[0] == "Attempted to exit cancel scope in a different task than it was entered in":
            # httpx_ws might try to close
            # the client
            return
        raise

@pytest.mark.asyncio
async def test_anon():

    async with create_web_client() as client:

        app = App()
        app.conn_client = WebsocketClient(client=client)

        new_session = []
        @app.on_open()
        async def join():
            new_session.append("new")

        asyncio.create_task(app.start())
        async with asyncio.timeout(5):
            while not new_session:
                await asyncio.sleep(0)
        assert new_session

@pytest.mark.asyncio
async def test_subscribe_anonymous(fake_ws_client):

    socket: WebsocketClient = WebsocketClient(client=fake_ws_client).from_init_channel(None)

    app = App()
    app.conn_client = WebsocketClient(client=fake_ws_client)
    with ExitStack() as app_stack:
        async with asyncio.TaskGroup() as tg:
            try:
                async with socket.connect() as connection:
                    async for msg in app._listen_start(echo_link=False, task_group=tg, app_stack=app_stack):
                        assert msg.request_id == "1234"
                        assert msg.channel == "http://localhost:5000/api/v1/streams/apps/session/unregistered/app-1234/1234"
                        app._close_listen_start = True
                        for _ in range(6):
                            await asyncio.sleep(0)
            except RuntimeError as exc:
                if exc.args[0].startswith("Attempted to exit a cancel scope that isn't the current tasks's current cancel scope"):
                    # We don't care if "aexit" wasn't called in the connection
                    return
                raise
