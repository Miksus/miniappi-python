import json
import time
from datetime import timedelta
import asyncio
from typing import Callable
from contextlib import asynccontextmanager

import pytest

from miniappi.core.stream import Streamer
from miniappi.core.stream.session import StreamSession
from miniappi.core.stream.exceptions import CloseStreamException
from miniappi.core.stream.connection import Message
from miniappi.testing.external import listen

@pytest.mark.asyncio
async def test_send_receive(mock_server):
    stream = Streamer(
        channel="mychannel:start",
    )

    @stream.on_open(pass_session=True)
    async def send_messages(session):
        await session.send({"msg": "from stream"})

    asyncio.create_task(stream.start())
    async with listen(
        stream,
        request_id="myrequest",
    ) as handler:
        await handler.send_message({"msg": "to stream"})
    
    assert len(handler.received)
    assert len(handler.sent)

@pytest.mark.asyncio
async def test_multiple_sessions(mock_server):
    stream = Streamer(
        channel="mychannel",
    )

    @stream.on_open(pass_session=True)
    async def send_messages(session: StreamSession):
        # Wait till 2 sessions are open
        while len(stream.sessions) != 2:
            await asyncio.sleep(0)
        await session.send({"msg": f"sent {session.start_args.request_id}"})

    asyncio.create_task(stream.start())
    async with listen(
        stream,
        request_id="1",
    ) as handler_1:
        async with listen(
            stream,
            request_id="2",
        ) as handler_2:
            await handler_2.send_message({"msg": "received 2"})
            await handler_1.send_message({"msg": "received 1"})

    assert [msg for msg in handler_1.received] == [Message(channel='mychannel', request_id="1", data={'msg': 'received 1'})]
    assert [msg for msg in handler_2.received] == [Message(channel='mychannel', request_id="2", data={"msg": "received 2"})]
    assert [msg for msg in handler_1.sent] == [Message(channel='mychannel', request_id="1", data={"msg": "sent 1"})] 
    assert [msg for msg in handler_2.sent] == [Message(channel='mychannel', request_id="2", data={"msg": "sent 2"})]

@pytest.mark.asyncio
async def test_callbacks(mock_server):
    stream = Streamer(
        channel="mychannel:start",
    )

    called = []

    @stream.on_start()
    async def run_func():
        called.append("on_start")

    @stream.on_open(pass_session=True)
    async def run_func(session: StreamSession):
        called.append("on_open")
        await session.send({"msg": "from stream"})

        while "on_message" not in called:
            await asyncio.sleep(0)
        raise RuntimeError("Random error")

    @stream.on_message()
    async def run_func(msg: Message):
        called.append("on_message")

    @stream.on_close()
    async def run_func(exc_type, exc, tb):
        assert exc_type is ExceptionGroup
        assert isinstance(exc, ExceptionGroup)
        assert tb
        called.append("on_close")

    @stream.on_end()
    async def run_func(exc_type, exc, tb):
        assert exc_type is ExceptionGroup
        assert isinstance(exc, ExceptionGroup)
        assert tb
        called.append("on_end")

    asyncio.create_task(stream.start())
    #with pytest.raises(ExceptionGroup):
    async with listen(
        stream,
        request_id="1234",
        wait_close=True,
    ) as handler:
        await handler.send_message({"msg": "to stream"})

    assert called == [
        "on_start",
        "on_open",
        "on_message",
        "on_close",
        "on_end",
    ]

@pytest.mark.asyncio
async def test_session_attrs(mock_server):
    stream = Streamer(
        channel="mychannel:start",
    )

    @stream.on_open(pass_session=True)
    async def send_messages(session: StreamSession):
        assert session.callbacks_message is stream.callbacks_message

    asyncio.create_task(stream.start())
    async with listen(
        stream,
        request_id="1234",
    ) as handler:
        await handler.send_message({"msg": "to stream"})

