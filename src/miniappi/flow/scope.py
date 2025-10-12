from miniappi.core.app import app_context, user_context

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
