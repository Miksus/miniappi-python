from typing import Literal
from miniappi.core.app import app_context, user_context
from miniappi.core.app import AppSession

type Scopes = Literal["app", "user", "auto"]

def in_channel_scope() -> bool:
    """Return true if in channel scope
    (called from a function of channel open)"""
    try:
        user_context.session
    except LookupError:
        return False
    else:
        return True

def in_app_scope() -> bool:
    """Return true if in app scope
    (called from a function of app running)"""
    try:
        app_context.app
    except LookupError:
        return False
    else:
        return True

def _get_sessions(session: AppSession | None = None, scope: Scopes = "auto"):
    if scope == "app":
        sessions = app_context.sessions.values()
    elif scope == "user":
        sessions = [user_context.session]
    elif scope == "auto":
        try:
            session = user_context.session
        except LookupError:
            # Called outside of channel
            # --> set as root to all channels
            sessions = app_context.sessions.values()
        else:
            sessions = [session]
        return sessions
    else:
        raise ValueError(scope)