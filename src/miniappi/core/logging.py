import logging
from enum import StrEnum

class Loggers(StrEnum):
    user_connection = "miniappi.core.connection.user"
    app_connection = "miniappi.core.connection.app"
    connection = "miniappi.core.connection"
