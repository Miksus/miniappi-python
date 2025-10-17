from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    "Miniappi configuration"
    model_config = SettingsConfigDict(
        env_prefix='miniappi_'
    )

    url_start: str = "https://miniappi.com/api/v1/streams/apps/start"
    url_apps: str = "https://miniappi.com/apps"

    echo_url: bool | None = True

settings = Settings()
