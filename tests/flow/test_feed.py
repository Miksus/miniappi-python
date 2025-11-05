import json
import time
from datetime import timedelta
import asyncio
from typing import Callable
from contextlib import asynccontextmanager

import pytest

from miniappi import App
from miniappi.testing.external import listen
from miniappi.ref import Feed
from miniappi import content, user_context

def test_defaults():
    feed = Feed[str](id="myref")
    assert feed.limit == 20
    assert feed.method == "fifo"
    assert feed.scope == "auto"
    assert feed.reference == "myref"
    assert Feed().reference != Feed().reference

    assert feed.model_dump() == {
        "type": "array",
        "data": [],
        "limit": 20,
        "method": "fifo",
        "reference": "myref"
    }

@pytest.mark.asyncio
async def test_feed(mock_server):
    app = App()
    feed = Feed[str](["old-1", "old-2"], id="myfeed")
    ready = asyncio.Event()

    @app.on_open()
    async def run_app():
        cont = content.v0.layouts.Column(
            id="my-col",
            contents=feed
        )
        await cont.show()
        await feed.append("new-1")
        ready.set()

    asyncio.create_task(app.start())
    async with listen(
        app,
        request_id="1",
    ) as handler:
        await ready.wait()

    # TODO: remove this ID
    assert handler.sent[0].data["data"]["contents"] == {
        'data': ["old-1", "old-2"],
        'limit': 20,
        'method': 'fifo',
        'reference': 'myfeed',
        'type': 'array'
    }
    assert handler.sent[1].data == {
        'data': 'new-1',
        'id': 'myfeed',
        'method': 'push',
        'type': 'ref'
    }
    assert feed.data == ["old-1", "old-2", "new-1"]

async def test_fifo(mock_server):
    app = App()
    feed = Feed[str](["old-1", "old-2", "old-3", "old-4"], method="fifo", limit=3, id="myfeed")
    assert feed.data == ["old-2", "old-3", "old-4"]
    ready = asyncio.Event()

    @app.on_open()
    async def run_app():
        cont = content.v0.layouts.Column(
            id="my-col",
            contents=feed
        )
        await cont.show()
        await feed.append("new-1")
        assert feed.data == ["old-3", "old-4", "new-1"]
        ready.set()

    asyncio.create_task(app.start())
    async with listen(
        app,
        request_id="1",
    ) as handler:
        await ready.wait()

async def test_lifo(mock_server):
    app = App()
    feed = Feed[str](["old-1", "old-2", "old-3", "old-4"], method="lifo", limit=3, id="myfeed")
    assert feed.data == ["old-1", "old-2", "old-3"]
    ready = asyncio.Event()

    @app.on_open()
    async def run_app():
        cont = content.v0.layouts.Column(
            id="my-col",
            contents=feed
        )
        await cont.show()
        await feed.append("new-1")
        assert feed.data == ["old-1", "old-2", "old-3"]
        ready.set()

    asyncio.create_task(app.start())
    async with listen(
        app,
        request_id="1",
    ) as handler:
        await ready.wait()

@pytest.mark.asyncio
async def test_app_scope(mock_server):
    app = App()
    feed = Feed[str](["old-1", "old-2"], id="myfeed", scope="app")
    ready_1 = asyncio.Event()
    ready_2 = asyncio.Event()

    @app.on_open()
    async def run_app():
        cont = content.v0.layouts.Column(
            id="my-col",
            contents=feed
        )
        await cont.show()
        if user_context.request_id == "1":
            await ready_2.wait()
            await feed.append(f"new-{user_context.request_id}")
            ready_1.set()
        if user_context.request_id == "2":
            ready_2.set()

    asyncio.create_task(app.start())
    async with listen(
        app,
        request_id="1",
    ) as handler_1:
        async with listen(
            app,
            request_id="2",
        ) as handler_2:
            await ready_1.wait()
            await ready_2.wait()
    
    assert handler_1.sent[1].data == {
        'data': 'new-1',
        'id': 'myfeed',
        'method': 'push',
        'type': 'ref'
    }
    assert handler_2.sent[1].data == {
        'data': 'new-1',
        'id': 'myfeed',
        'method': 'push',
        'type': 'ref'
    }
    assert len(handler_2.sent) == len(handler_1.sent)

@pytest.mark.asyncio
async def test_user_scope(mock_server):
    app = App()
    ready_1 = asyncio.Event()
    ready_2 = asyncio.Event()

    feeds = {}

    @app.on_open()
    async def run_app():
        if user_context.request_id == "1":
            feed = Feed[str]([], id="myfeed", scope="user")
            feeds["1"] = feed
            ready_1.set()
        if user_context.request_id == "2":
            await ready_1.wait()
            # Should show only for user-1
            await feeds["1"].append(f"new-{user_context.request_id}")
            ready_2.set()

    asyncio.create_task(app.start())
    async with listen(
        app,
        request_id="1",
    ) as handler_1:
        async with listen(
            app,
            request_id="2",
        ) as handler_2:
            await ready_1.wait()
            await ready_2.wait()
    
    assert handler_1.sent[0].data == {
        'data': 'new-2',
        'id': 'myfeed',
        'method': 'push',
        'type': 'ref'
    }
    assert handler_2.sent == []

@pytest.mark.asyncio
async def test_auto_scope(mock_server):
    app = App()
    ready_2 = asyncio.Event()
    ready = asyncio.Event()

    feed = Feed[str]([], id="myfeed", scope="auto")

    @app.on_start()
    async def run_app():
        await ready_2.wait()
        await feed.append(f"new-all")
        ready.set()

    @app.on_open()
    async def run_app():
        await feed.append(f"new-{user_context.request_id}")
        if user_context.request_id == "2":
            ready_2.set()

    asyncio.create_task(app.start())
    async with listen(
        app,
        request_id="1",
    ) as handler_1:
        async with listen(
            app,
            request_id="2",
        ) as handler_2:
            await ready.wait()
    
    assert len(handler_1.sent) == len(handler_2.sent)
    assert handler_1.sent[0].data == {
        'data': 'new-1',
        'id': 'myfeed',
        'method': 'push',
        'type': 'ref'
    }
    assert handler_1.sent[1].data == {
        'data': 'new-all',
        'id': 'myfeed',
        'method': 'push',
        'type': 'ref'
    }
