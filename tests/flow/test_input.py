import json
import time
from datetime import timedelta
import asyncio
from typing import Callable
from contextlib import asynccontextmanager

import pytest

from miniappi.core.app import App, user_context
from miniappi.core.stream.session import StreamSession
from miniappi.core.stream.exceptions import CloseStreamException
from miniappi.testing.external import listen
from miniappi.flow.app import temp_app
from miniappi import content

@pytest.mark.asyncio
async def test_user_input(mock_server):
    app = App()

    inputs = []

    cont = content.v0.widgets.Button(label="Press me")

    @app.on_open()
    async def run_app():
        await cont.show()
        inputs.append(await cont.wait_input())

    asyncio.create_task(app.start())
    async with listen(
        app,
        request_id="1",
    ) as handler:
        await handler.send_message({
            "id": cont.id,
        })

    assert inputs == [{"id": cont.id}]

@pytest.mark.asyncio
async def test_user_input_any_child(mock_server):
    app = App()

    inputs = []
    Column = content.v0.layouts.Column
    button = content.v0.widgets.Button(label="Press me")
    cont = Column(
        contents=[
            button
        ]
    )

    @app.on_open()
    async def run_app():
        await cont.show()
        inputs.append(await cont.wait_input())

    asyncio.create_task(app.start())
    async with listen(
        app,
        request_id="1",
    ) as handler:
        await handler.send_message({
            "id": button.id,
        })

    assert inputs == [{"id": button.id}]

@pytest.mark.asyncio
async def test_user_input_wait_all(mock_server):
    app = App()

    inputs = []

    cont = content.v0.widgets.Button(label="Press me")
    is_ready = asyncio.Event()
    @app.on_start()
    async def run_app():
        
        inputs.append(await cont.wait_input())
        is_ready.set()

    asyncio.create_task(app.start())
    async with listen(
        app,
        request_id="1",
    ) as user_1:
        async with listen(
            app,
            request_id="2",
        ) as user_2:
            await user_1.send_message({
                "id": cont.id,
                "value": "user_1"
            })
            await user_2.send_message({
                "id": cont.id,
                "value": "user_2"
            })
            await is_ready.wait()

    assert inputs == [
        {
            "1": {"id": cont.id, "value": "user_1"},
            "2": {"id": cont.id, "value": "user_2"},
        }
    ]

@pytest.mark.asyncio
async def test_user_input_wait_any(mock_server):
    app = App()

    inputs = []

    cont = content.v0.widgets.Button(label="Press me")
    is_ready = asyncio.Event()
    @app.on_start()
    async def run_app():
        inputs.append(await cont.wait_input(wait_for="any"))
        is_ready.set()

    asyncio.create_task(app.start())
    async with listen(
        app,
        request_id="1",
    ) as user_1:
        async with listen(
            app,
            request_id="2",
        ) as user_2:
            await user_1.send_message({
                "id": cont.id,
                "value": "user_1"
            })
            await is_ready.wait()

    assert inputs == [
        {
            "1": {"id": cont.id, "value": "user_1"},
        }
    ]
