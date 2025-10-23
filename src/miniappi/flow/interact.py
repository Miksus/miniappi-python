import asyncio
from typing import Generic, TypeVar, Literal
from collections import UserList
from ..core.app import BaseContent, user_context, app_context, PushRight
from miniappi.core.connection import Message
from miniappi.flow import temp_app, in_channel_scope, in_app_scope

async def wait_for_input(content: BaseContent, show: bool = False, any_child=True, wait_for: Literal["any", "all"] | None = None):
    """Wait for input to the content
    
    If not in channel context, wait for all input"""
    def set_if_ready():
        if wait_for == "all" or (wait_for is None and not in_channel):
            for session in app_context.sessions.values():
                if session.request_id not in outputs:
                    # Not all ready, don't set the event
                    return
        event.set()

    def get_child_ids():
        return [c.id for c in content.iter_content()]

    in_channel = in_channel_scope()

    only_caller = in_channel and wait_for is None
    caller_request_id = user_context.request_id if in_channel else None

    ids = content.id if not any_child else get_child_ids() + [content.id]
    event = asyncio.Event()
    outputs = {}
    with temp_app() as app:
        @app.on_message()
        async def get_message(msg: Message):
            data: dict = msg.data
            if data.get("id") in ids:
                if only_caller and msg.request_id != caller_request_id:
                    return
                # We don't need the content ID with
                # the msg so we just return data
                outputs[msg.request_id] = data
                set_if_ready()
        if show:
            await content.show()
        await event.wait()

    if only_caller:
        return outputs[caller_request_id]
    return outputs
