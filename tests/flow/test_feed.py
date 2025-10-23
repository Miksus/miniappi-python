import json
import time
from datetime import timedelta
import asyncio
from typing import Callable
from contextlib import asynccontextmanager

import pytest

from miniappi import App
from miniappi.testing.external import listen
from miniappi.flow import Feed
from miniappi import content

@pytest.mark.asyncio
async def test_feed(mock_server):
    app = App()
    feed = Feed[str](id="myfeed")
    ready = asyncio.Event()

    @app.on_open()
    async def run_app():
        cont = content.v0.layouts.Column(
            id="my-col",
            contents=feed.as_reference()
        )
        await cont.show()
        await feed.append("a")
        ready.set()

    asyncio.create_task(app.start())
    async with listen(
        app,
        request_id="1",
    ) as handler:
        await ready.wait()

    # TODO: remove this ID
    cont_id = handler.sent[0].data["data"]["contents"]["id"]

    assert handler.sent[0].data == {
        'data': {
            'contentType': 'v0/layouts/Column.vue',
            'contents': {
                'data': [],
                'id': cont_id,
                'reference': 'myfeed',
            },
            'id': 'my-col',
        },
        'method': 'put',
        'type': 'root'
    }
    assert handler.sent[1].data == {
        'data': 'a',
        'id': 'myfeed',
        'method': 'push',
        'type': 'ref'
    }
