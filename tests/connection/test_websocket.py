from miniappi.core.stream.connection import (
    WebsocketStartArgs,
    WebsocketConnection,
    WebsocketChannel,
    WebsocketClient
)
import pytest
import httpx
from httpx_ws.transport import ASGIWebSocketTransport
from starlette.websockets import WebSocket
from starlette.applications import Starlette
from starlette.responses import HTMLResponse
from starlette.routing import Route, WebSocketRoute

async def endpoint_start_app(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_json("app-1234")

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
async def test_app_start_anon(fake_ws_client):

    socket: WebsocketChannel = WebsocketClient(client=fake_ws_client).from_init_channel(None)

    async with socket.connect() as conn:
        async for startargs in conn.listen_start():
            break
        
        assert socket.app_name == "app-1234"
        assert socket.app_url == "https://miniappi.com/apps/app-1234"
    assert startargs.request_id == "1234"
    assert startargs.channel == "http://localhost:5000/api/v1/streams/apps/session/unregistered/app-1234/1234"

@pytest.mark.asyncio
async def test_session_start(fake_ws_client):

    socket: WebsocketChannel = WebsocketClient(client=fake_ws_client).from_start_args(
        WebsocketStartArgs(
            request_id="1234",
            channel="http://localhost:5000/api/v1/streams/apps/session/unregistered/app-1234/1234"
        )
    )
    ... # TODO
