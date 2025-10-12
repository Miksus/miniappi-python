import asyncio

import pytest

from miniappi.core.app import App, AppSession, user_context, BaseContent
from miniappi.core.app.message_types import PutRoot
from miniappi.core.stream.session import StreamSession
from miniappi.flow.interact import wait_for_input

from miniappi.testing.external import listen
from miniappi.content import Loading

@pytest.mark.asyncio
async def test_send_content(mock_server):
    stream = App()

    @stream.on_open(pass_session=True)
    async def send_messages(session: AppSession):
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
