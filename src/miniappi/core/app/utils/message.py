from typing import Dict
from miniappi.core.app.context import CurrentContent
from miniappi.core.app.models import BaseContent
from miniappi.core.app.message_types import InputMessage, PutRoot

def handle_message(curr_content: CurrentContent, msg: InputMessage):

    if msg.type == "root":
        curr_content.root = msg.data
    elif msg.type == "ref":
        reference = curr_content.references[msg.id]

        if msg.method == "put":
            curr_content.references[msg.id] = msg.data
        elif msg.method == "delete":
            curr_content.references.pop(msg.id, None)
        elif msg.method == "push":
            push_reference(curr_content.references, msg)
        elif msg.method == "pop":
            pop_reference(curr_content.references, msg)
        else:
            raise ValueError(f"unrecognized method: {msg.method}")

def push_reference(references: Dict[str, any], msg: InputMessage):
    reference = references[msg.id]
    if isinstance(reference, list):
        if msg.key is None:
            reference.append(msg.data)
        else:
            reference.insert(msg.key, msg.data)
    elif isinstance(reference, dict):
        if msg.key is None:
            raise KeyError("Key undefined")
        else:
            reference[msg.key] = msg.data

def pop_reference(references: Dict[str, any], msg: InputMessage):
    reference = references[msg.key]
    if isinstance(msg.key, int):
        reference: list
        reference.pop(msg.key)
    elif isinstance(reference, dict):
        reference.pop(msg.key)
