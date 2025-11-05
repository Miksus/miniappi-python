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
from miniappi import content

def test_defaults():
    feed = Feed[str]()
    assert feed.limit == 20
    assert feed.method == "fifo"
    assert isinstance(feed.reference, str)
    assert Feed().reference != Feed().reference

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
