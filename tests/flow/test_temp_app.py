import json
import time
from datetime import timedelta
import asyncio
from typing import Callable
from contextlib import asynccontextmanager

import pytest

from miniappi.core import App, user_context
from miniappi.testing.external import listen
from miniappi.flow.app import temp_app

@pytest.mark.asyncio
async def test_app_level_on_message(mock_server):
    stream = App()

    called = {
        "1": 0
    }

    finish_temp = asyncio.Event()

    @stream.on_start()
    async def run_app():
        with stream.temp() as app:
            @app.on_message()
            async def run_example(msg):
                called[user_context.request_id] += 1
            await finish_temp.wait()

    asyncio.create_task(stream.start())
    async with listen(
        stream,
        request_id="1",
    ) as handler:
        assert [
            cb.func.__name__
            for cb in  stream.callbacks_message
        ] == ["record_message", "run_example"]

        await handler.send_message({"msg": "to stream"})
        await handler.send_message({"msg": "to stream"})
        await handler.wait_for_received()

        # After thism the temporary on_message
        # should be deleted
        finish_temp.set()

        await handler.send_message({"msg": "to stream"})
    
    assert called["1"] == 2
    assert [
        cb.func.__name__
        for cb in  stream.callbacks_message
    ] == ["record_message"]
