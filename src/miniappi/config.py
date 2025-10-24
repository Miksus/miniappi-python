from pathlib import Path
from importlib.metadata import version, PackageNotFoundError
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    "Miniappi configuration"
    model_config = SettingsConfigDict(
        env_prefix='miniappi_'
    )

    url_start: str = "https://miniappi.com/api/v1/streams/apps/start"
    url_recover: str = "https://miniappi.com/api/v1/streams/apps/recover"
    url_apps: str = "https://miniappi.com/apps"

    echo_url: bool | None = True

    keepalive_ping_interval: float | None = 20.0
    keepalive_ping_timeout: float | None = 20.0
    timeout: float | None = None

    @property
    def version(self):
        "Version of Miniappi"
        try:
            return version("miniappi")
        except PackageNotFoundError:
            # Probably run in dev
            return "0.0.0"

settings = Settings()
