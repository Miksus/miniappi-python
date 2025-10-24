import asyncio
from uuid import uuid4
import urllib.parse
import json
from dataclasses import asdict
from miniappi.core.connection.websocket import (
    WebsocketUserConnection,
    WebsocketClient
)
from miniappi import content
from contextlib import ExitStack, asynccontextmanager
from typing import List
from functools import partial
import pytest
import httpx
from httpx_ws.transport import ASGIWebSocketTransport
from miniappi import App, app_context, settings
from miniappi.core.connection.websocket import WebsocketUserSessionArgs, ServerConf, RecoveryConf

from starlette.websockets import WebSocket
from starlette.applications import Starlette
from starlette.responses import HTMLResponse
from starlette.routing import Route, WebSocketRoute


class WebApp:

    def __init__(self, requests: List[str], interactions: List[str]):
        self.requests: List[str] = requests
        self.interactions = interactions

        self.app_name = str(uuid4())

        self.n_open = 0
        self.contents = []
        self.client = None
        self._close = False
        self.initdata = None

    async def app_session(self, websocket: WebSocket):
        self.n_open += 1
        await websocket.accept()
        app_name = self.app_name
        self.initdata = await websocket.receive_json()

        # Init
        await websocket.send_json(asdict(
            ServerConf(
                app_name=app_name,
                app_url=f"{settings.url_apps}/{app_name}"
            )
        ))

        await self.begin_sessions(websocket, app_name=app_name)

    async def begin_sessions(self, websocket: WebSocket, app_name: str):

        # recovery
        recovery_key = str(uuid4())
        await websocket.send_json(asdict(
            RecoveryConf(
                recovery_key=recovery_key
            )
        ))
        for request_id in self.requests:
            await self.begin_session(websocket, request_id=request_id, app_name=app_name)
            await asyncio.sleep(0)
        await websocket.close()
        self.n_open -= 1

    async def begin_session(self, websocket: WebSocket, request_id, app_name):
        # Sessions
        url = urllib.parse.urlparse(settings.url_start)
        await websocket.send_json(asdict(
            WebsocketUserSessionArgs(
                request_id=request_id,
                user_url=f"{url.scheme}://{url.netloc}/v1/streams/apps/sessions/{app_name}/{request_id}"
            )
        ))

    async def user_session(self, websocket: WebSocket, app_name: str, request_id: str):
        self.n_open += 1
        await websocket.accept()
        async def _receive_messages():
            while True:
                msg = await websocket.receive_text()
                self.contents.append(msg)
                if self._close:
                    await websocket.close()
                    return
                await asyncio.sleep(0)

        async def _send_messages():
            for msg in self.interactions:
                await websocket.send_text(msg)


        tasks: List[asyncio.Task] = [
            asyncio.create_task(_receive_messages()),
            asyncio.create_task(_send_messages())
        ]
        while True:
            if self._close:
                for t in tasks:
                    t.cancel()
                break
            await asyncio.sleep(0)
        await websocket.close()
        self.n_open -= 1

    def create_app(self):
        start_path = urllib.parse.urlparse(settings.url_start).path

        user_routes = [
            WebSocketRoute(
                f"/v1/streams/apps/sessions/{self.app_name}/{request_id}",
                partial(self.user_session, app_name=self.app_name, request_id=request_id)
            )
            for request_id in self.requests
        ]

        return Starlette(
            routes=[
                *user_routes,
                WebSocketRoute(start_path, self.app_session),
            ],
        )

    @asynccontextmanager
    async def enter_client(self):
        webapp = self.create_app()
        transport = ASGIWebSocketTransport(webapp)
        async with httpx.AsyncClient(transport=transport, headers={'host': 'example.org'}) as client:
            self.client = client
            try:
                yield client
                # See: https://github.com/frankie567/httpx-ws/discussions/79#discussioncomment-12205278
            finally:
                transport.exit_stack = None
                await asyncio.sleep(0)


    async def close(self):
        self._close = True
        while self.n_open > 0:
            await asyncio.sleep(0.0)


@pytest.mark.asyncio
async def test_anon():
    webapp = WebApp(
        requests=["1234"],
        interactions=[json.dumps({
            "id": "1234",
            "value": "pressed"
        })]
    )
    async with webapp.enter_client() as client:

        app = App()
        received = []
        has_joined = asyncio.Event()
        has_interacted = asyncio.Event()
        app.conn_client = WebsocketClient(client=client)

        @app.on_open()
        async def join():
            await content.v0.Title(
                id="a-title",
                text="Some text"
            ).show()
            has_joined.set()

        @app.on_message()
        async def new_message(msg):
            received.append(msg)
            has_interacted.set()

        asyncio.create_task(app.start())
        async with asyncio.timeout(60 *5):
            await has_joined.wait()
            await has_interacted.wait()
        await webapp.close()
        
        while app.is_running:
            await asyncio.sleep(0)

        assert [
            "a-title"
        ] ==  [
            json.loads(cont)["data"]["id"]
            for cont in webapp.contents
        ]
        assert [
            {'id': '1234', 'value': 'pressed'}
        ] == [
            msg.data
            for msg in received
        ]
