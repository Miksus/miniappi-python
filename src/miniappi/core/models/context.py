import inspect
import dataclasses
from uuid import uuid4
from typing import Any, Optional, Generic, TypeVar, Dict
from contextvars import copy_context
from collections import UserDict
from contextlib import contextmanager
from contextvars import ContextVar, Token

ContextDataT = TypeVar("ContextDataT")

class Context(Generic[ContextDataT]):

    def __init__(self, name: str):
        self.store: ContextVar[ContextDataT] = ContextVar(
            name
        )

    @property
    def data(self) -> ContextDataT:
        return self.store.get()

    def exists(self) -> bool:
        return self.store in copy_context()

    @contextmanager
    def enter(self, data: ContextDataT):
        "Enter context"
        if self.exists():
            raise LookupError("Context already initiated")

        token: Token = self.store.set(data)
        yield self.store
        self.store.reset(token)

    def __repr__(self) -> str:
        try:
            return f"<{__name__}.{self.__class__.__name__} {self.data}>"
        except LookupError:
            return f"<{__name__}.{self.__class__.__name__}>"

    def __str__(self) -> str:
        try:
            return str(self.data)
        except LookupError:
            return str({})

class ContextDict(Context[Dict[Any, Any]], UserDict):

    def enter(self, data: Optional[Dict] = None):
        if data is None:
            data = {}
        return super().enter(data.copy())

MISSING = dataclasses.MISSING

class ContextModel(Context[Dict[Any, Any]]):
    __ignore_extra__: bool = False

    def __init__(self, name_: str | None = None, **kwargs):
        if name_ is None:
            name_ = str(uuid4())
        self.store: ContextVar[ContextDataT] = ContextVar(
            name_
        )
        self._set_attrs(**kwargs)

    def _set_attrs(self, **kwargs):
        attrs = inspect.get_annotations(type(self))
        fields: Dict[str, dataclasses.Field] = {}
        for name, type_ in attrs.items():
            try:
                default = super().__getattribute__(name)
            except AttributeError:
                default = MISSING
            if isinstance(default, dataclasses.Field):
                fields[name] = default
            else:
                field = dataclasses.field()
                field.name = name
                field.default = default
                field.type = type_
                fields[name] = field
            if name in kwargs:
                field.default = kwargs[name]
        self.__fields__ = fields

    def enter(self, data: Optional[Dict] = None):
        defaults = {
            name: field.default if field.default is not MISSING else field.default_factory()
            for name, field in self.__fields__.items()
            if (
                field.default is not MISSING
                or field.default_factory is not MISSING
            )
        }
        if data is None:
            data = {}
        elif not self.__ignore_extra__:
            extra_fields = [
                field
                for field in data
                if field not in self.__fields__
            ]
            if extra_fields:
                raise TypeError(f"'{type(self)}' has no attribute(s): {', '.join(extra_fields)}")
        data = {**defaults, **data}

        missing_fields = [
            field_name
            for field_name in self.__fields__
            if field_name not in data
        ]
        if missing_fields:
            raise TypeError(f'Missing required argument(s): {", ".join(missing_fields)}')
        return super().enter(data)

    def __getattribute__(self, key: str):
        try:
            fields = super().__getattribute__("__fields__")
        except AttributeError:
            return super().__getattribute__(key)

        if key in fields:
            value = self.data[key]
            return value
        return super().__getattribute__(key)

    def __setattr__(self, name: str, value):
        if name in ("store",) or name.startswith("_"):
            return super().__setattr__(name, value)
        if name not in self.__fields__:
            self._raise_attr_error(name)
        self.data[name] = value

    def _raise_attr_error(self, name: str):
        raise AttributeError(f"'{type(self)!s}' object has no attribute '{name}'")
