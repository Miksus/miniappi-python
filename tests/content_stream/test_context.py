import asyncio
from dataclasses import dataclass

import pytest

from miniappi import settings
from miniappi.core.models.context import ContextModel

from miniappi.core import App, user_context, app_context, Session
from miniappi.core.models.message_types import PutRoot
from miniappi.core.connection import Message

from miniappi.testing.external import listen
from miniappi.content import Loading

@pytest.mark.asyncio
async def test_app_context(mock_server):

    stream = App()

    called = []
    is_ready = asyncio.Event()

    @stream.on_start()
    async def run_func():
        is_ready.set()
        assert app_context.sessions is stream.sessions
        assert app_context.app_url == f"{settings.url_apps}/{app_context.app_name}"
        assert isinstance(app_context.app_name, str)
        assert app_context.extra == {}
        called.append("on_start")

    task = asyncio.create_task(stream.start())
    async with listen(
        stream,
        request_id="1",
    ) as handler_1:
        await is_ready.wait()

    assert called

@pytest.mark.asyncio
async def test_user_context(mock_server):
    stream = App()

    called = []
    is_ready = asyncio.Event()

    @stream.on_open()
    async def run_func():
        is_ready.set()
        assert user_context.session.request_id == "1"
        assert user_context.request_id == "1"
        assert user_context.extra == {}
        called.append("on_open")

    task = asyncio.create_task(stream.start())
    async with listen(
        stream,
        request_id="1",
    ) as handler_1:
        await is_ready.wait()

    assert called

@pytest.mark.asyncio
async def test_multiple_access(mock_server):
    # Test multiple sessions won't mix up global context
    # variable
    stream = App()
    event_both_open = asyncio.Event()

    obs_context_from_request = []
    @stream.on_message()
    async def receive_messages(msg: Message):
        await event_both_open.wait()
        obs_context_from_request.append(
            user_context.request_id
        )

    obs_context_from_response = []
    @stream.on_open()
    async def send_messages():
        await event_both_open.wait()
        assert isinstance(user_context.session, Session)
        obs_context_from_response.append(
            user_context.request_id
        )

    asyncio.create_task(stream.start())
    async with listen(
        stream,
        request_id="1",
    ) as handler_1:
        async with listen(
            stream,
            request_id="2"
        ) as handler_2:
            event_both_open.set()
            await handler_2.send_message({"msg": "received 2"})
            await asyncio.sleep(0)
            await handler_1.send_message({"msg": "received 1"})

    # Note the stream "1" started the stream
    # first but stream 2 replied first thus
    # the ordering
    assert obs_context_from_response == [
        "1", "2",
    ]
    assert obs_context_from_request == [
        "2", "1",
    ]

@pytest.mark.asyncio
async def test_context_access(mock_server):

    stream = App()

    called = []

    @stream.on_start()
    async def run_func():
        assert app_context.app
        with pytest.raises(LookupError):
            user_context.request_id
        called.append("on_start")

    @stream.on_open()
    async def run_func():
        assert app_context.app
        assert user_context.request_id
        called.append("on_open")
        await asyncio.sleep(0)

        while "on_message" not in called:
            await asyncio.sleep(0)
        raise RuntimeError("Intentional")

    @stream.on_message()
    async def run_func(msg: Message):
        assert app_context.app
        assert user_context.request_id
        called.append("on_message")

    @stream.on_close()
    async def run_func(*args):
        assert app_context.app
        assert user_context.request_id
        called.append("on_close")

    @stream.on_end()
    async def run_func(*args):
        assert app_context.app
        with pytest.raises(LookupError):
            user_context.request_id
        called.append("on_end")

    task = asyncio.create_task(stream.start())
    async with listen(
        stream,
        request_id="123",
        wait_close=True
    ) as handler_1:
        await handler_1.send_message({"msg": "received 1"})

    assert called == [
        "on_start",
        "on_open",
        "on_message",
        "on_close",
        "on_end",
    ]

@pytest.mark.asyncio
async def test_custom_init(mock_server):
    class MyAppContext(ContextModel):
        name: str = "random app"
        a_value: int
        default_field: str = "default value"
    
    ctx = MyAppContext(
        name="the app",
        a_value=1
    )
    assert ctx.__fields__["name"].name == "name"
    assert ctx.__fields__["name"].type is str
    assert ctx.__fields__["name"].default == "the app"

    assert ctx.__fields__["a_value"].name == "a_value"
    assert ctx.__fields__["a_value"].type is int
    assert ctx.__fields__["a_value"].default == 1

    assert ctx.__fields__["default_field"].name == "default_field"
    assert ctx.__fields__["default_field"].type is str
    assert ctx.__fields__["default_field"].default == "default value"

@pytest.mark.asyncio
async def test_custom_context(mock_server):
    class MyAppContext(ContextModel):
        name: str = "an app"
        changed: int = 0

    class MyChannelContext(ContextModel):
        name: str = "a channel"
        changed: int = 0

    my_app_context = MyAppContext()
    my_channel_context = MyChannelContext()
    stream = App(
        app_context=my_app_context,
        user_context=my_channel_context
    )

    called = []
    is_ready = asyncio.Event()

    @stream.on_start()
    async def run_func():
        
        assert my_app_context.name == "an app"
        with pytest.raises(LookupError):
            my_channel_context.name

        my_app_context.changed += 1
        assert my_app_context.changed == 1

        called.append("on_start")

    @stream.on_open()
    async def run_func():
        assert my_app_context.name == "an app"
        assert my_channel_context.name == "a channel"

        my_app_context.changed += 1
        assert my_app_context.changed == 2

        my_channel_context.changed += 1
        assert my_channel_context.changed == 1

        called.append("on_open")

        while "on_message" not in called:
            await asyncio.sleep(0)
        raise RuntimeError("Intentional")

    @stream.on_message()
    async def run_func(msg: Message):
        assert my_app_context.name == "an app"
        assert my_channel_context.name == "a channel"

        my_app_context.changed += 1
        assert my_app_context.changed == 3

        my_channel_context.changed += 1
        assert my_channel_context.changed == 2

        called.append("on_message")
        is_ready.set()

    @stream.on_close()
    async def run_func(*args):
        assert my_app_context.name == "an app"
        assert my_channel_context.name == "a channel"

        my_app_context.changed += 1
        assert my_app_context.changed == 4

        my_channel_context.changed += 1
        assert my_channel_context.changed == 3

        called.append("on_close")

    @stream.on_end()
    async def run_func(*args):
        assert my_app_context.name == "an app"
        with pytest.raises(LookupError):
            my_channel_context.name

        my_app_context.changed += 1
        assert my_app_context.changed == 5

        called.append("on_end")

    task = asyncio.create_task(stream.start())
    async with listen(
        stream,
        request_id="123",
        wait_close=True
    ) as handler_1:
        await handler_1.send_message({"msg": "received 1"})
        await is_ready.wait()

    assert called == [
        "on_start",
        "on_open",
        "on_message",
        "on_close",
        "on_end",
    ]
