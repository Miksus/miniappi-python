import asyncio
from miniappi.core.stream.connection import (
    WebsocketStartArgs,
    WebsocketConnection,
    WebsocketChannel,
    WebsocketClient
)
from contextlib import ExitStack
import pytest
import httpx
from httpx_ws.transport import ASGIWebSocketTransport
from miniappi import App, app_context
from starlette.websockets import WebSocket
from starlette.applications import Starlette
from starlette.responses import HTMLResponse
from starlette.routing import Route, WebSocketRoute

async def endpoint_start_app(websocket: WebSocket):
    await websocket.accept()
    initdata = await websocket.receive_json()
    await websocket.send_json({
        "app_name": "my-app",
        "app_url": f"https://example.com/apps/my-app",
        "recovery_key": "1234",
    })

    # Send an actual request
    await websocket.send_json({
        "channel": "http://localhost:5000/api/v1/streams/apps/session/unregistered/app-1234/1234",
        "request_id": "1234"
    })
    await websocket.close()

async def endpoint_start_session(websocket: WebSocket):
    ...

webapp = Starlette(
    routes=[
        WebSocketRoute("/api/v1/streams/apps/session/unregistered/app-1234/1234", endpoint_start_session),
        WebSocketRoute("/api/v1/streams/apps/start", endpoint_start_app),
    ],
)

@pytest.fixture
async def fake_ws_client():
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
async def test_subscribe_anonymous(fake_ws_client):

    socket: WebsocketChannel = WebsocketClient(client=fake_ws_client).from_init_channel(None)

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
