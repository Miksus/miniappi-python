from copy import copy
from typing import TYPE_CHECKING, Any, Dict, Union
from dataclasses import dataclass, field
from miniappi.core.context import ContextModel

if TYPE_CHECKING:
    from .stream import AppSession
    from .models import BaseContent
    from .session import StreamSession
    from .stream import App


@dataclass
class CurrentContent:
    root: Union["BaseContent", None] = None
    references: Dict[str, "BaseContent"] = field(default_factory=lambda: {})

class UserContext(ContextModel):

    session: "AppSession" # Current stream session
    request_id: str
    extra: dict = field(default_factory=lambda: {})

    def copy(self):
        return copy(self)

class AppContext(ContextModel):

    app: "App"
    name: str
    app_url: str
    recovery_key: str
    sessions: Dict[str, "AppSession"]
    extra: dict = field(default_factory=lambda: {})

    def copy(self):
        return copy(self)

user_context = UserContext()
app_context = AppContext()
