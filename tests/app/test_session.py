import asyncio
from typing import List
import pytest

from miniappi.core import App, Session
from miniappi.core.connection import Message
from miniappi.core.models.message_types import PutRoot

from miniappi.testing.external import listen
from miniappi.content import Loading

@pytest.mark.asyncio
async def test_send_content(mock_server):
    stream = App()

    @stream.on_open(pass_session=True)
    async def send_messages(session: Session):
        await session.send(
            PutRoot(
                data=Loading(id="mycomp")
            )
        )

    asyncio.create_task(stream.start())
    async with listen(
        stream,
        request_id="1",
    ) as handler:
        ...

    assert [
        msg.data
        for msg in handler.sent
    ] == [
        {
            "type": "root",
            "method": "put", 
            "data": {
                "contentType": "Loading.vue",
                "id": "mycomp"
            }
        }
    ]

@pytest.mark.asyncio
async def test_receive_input(mock_server):
    stream = App()

    messages: List[Message] = []
    @stream.on_message()
    async def send_messages(message: Message):
        messages.append(message)

    asyncio.create_task(stream.start())
    async with listen(
        stream,
        request_id="1",
    ) as handler:
        await handler.send_message({
            "id": "my-button",
            "value": "pressed"
        })

    assert [
        msg.data
        for msg in messages
    ] == [
        {
            "id": "my-button",
            "value": "pressed"
        }
    ]
