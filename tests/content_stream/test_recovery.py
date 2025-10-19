import asyncio
from dataclasses import dataclass

import pytest

from miniappi.core.app import App, user_context, app_context
from miniappi.testing.external import listen, StreamHandler

@pytest.mark.asyncio
async def test_recover(mock_server):

    stream = App()

    called = []
    is_ready = asyncio.Event()
    can_continue = asyncio.Event()
    is_finished = asyncio.Event()

    recovery_keys = []

    @stream.on_open()
    async def run_func():
        recovery_keys.append(app_context.recovery_key)
        is_ready.set()
        await can_continue.wait()
        called.append(user_context.request_id)
        recovery_keys.append(app_context.recovery_key)
        if len(called) == 2:
            is_finished.set()

    task = asyncio.create_task(stream.start())
    async with listen(
        stream,
        request_id="1",
    ) as handler_1:
        await is_ready.wait()
        stream.conn_client.network_error_on_start = True

        # This request will be lost
        handler_lost = StreamHandler(
            stream=stream,
            request_id="2",
        )
        await handler_lost.start_communication()
        for _ in range(6):
            await asyncio.sleep(0)

        stream.conn_client.network_error_on_start = False

        # This request should not be lost
        async with listen(
            stream,
            request_id="3",
        ) as handler_3:
            can_continue.set()
            await is_finished.wait()

    assert called == ["1", "3"]
    # We should have two recovery keys
    assert len(set(recovery_keys)) > 1
