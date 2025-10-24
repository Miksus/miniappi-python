from contextlib import contextmanager
from miniappi.core import app_context

class TempApp:

    def __init__(self, app=None):
        self._app = app_context.app if app is None else app
        self._callbacks = {
            self._app.on_open: [],
            self._app.on_message: [],
            self._app.on_close: [],
            self._app.on_start: [],
            self._app.on_end: [],
        }

    def _get_app_callbacks(self, app_meth):
        return {
            self._app.on_open: self._app.callbacks_open,
            self._app.on_message: self._app.callbacks_message,
            self._app.on_close: self._app.callbacks_close,
            self._app.on_start: self._app.callbacks_start,
            self._app.on_end: self._app.callbacks_end,
        }[app_meth]

    def _on_callback(self, *args, _app_meth, **kwargs):
        on_init = _app_meth()
        def wrapper(func):
            out = on_init(func)
            # The app might create some wrapper
            # for the func (ie. see on_message)
            # so we get the last callback
            self._callbacks[_app_meth].append(
                self._get_app_callbacks(_app_meth)[-1]
            )
            return out
        return wrapper

    def on_start(self, *args, **kwargs):
        return self._on_callback(
            *args,
            **kwargs,
            _app_meth=self._app.on_start
        )

    def on_open(self, *args, **kwargs):
        return self._on_callback(
            *args,
            **kwargs,
            _app_meth=self._app.on_open
        )

    def on_message(self, *args, **kwargs):
        return self._on_callback(
            *args,
            **kwargs,
            _app_meth=self._app.on_message
        )

    def on_close(self, *args, **kwargs):
        return self._on_callback(
            *args,
            **kwargs,
            _app_meth=self._app.on_close
        )

    def on_end(self, *args, **kwargs):
        return self._on_callback(
            *args,
            **kwargs,
            _app_meth=self._app.on_end
        )

    def remove(self):
        "remove all set callbacks"
        for meth, setcbs in self._callbacks.items():
            for cb in setcbs:
                app_cbs = self._get_app_callbacks(meth)
                app_cbs.remove(cb)

@contextmanager
def temp_app(app=None):
    "Context manager for setting app configs temporarily (ie. callbacks)"
    handler = TempApp(app)
    yield handler
    handler.remove()
