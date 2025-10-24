
class StreamException(Exception):
    ...

    @classmethod
    def _only_this(cls, e_group: ExceptionGroup):
        for exc in e_group.exceptions:
            if not isinstance(exc, cls):
                return False
            if isinstance(exc, ExceptionGroup):
                if not cls._only_this(exc):
                    return False
        return True

class CloseSessionException(StreamException):
    ...

class CloseStreamException(StreamException):
    ...
