from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    "API settings (by default dev)"
    model_config = SettingsConfigDict(
        env_prefix='python_api_'
    )

    log_dir: Path = Path().cwd() / "logs"

    url_start: str = "https://miniappi.com/api/v1/streams/apps/start"
    url_apps: str = "https://miniappi.com/apps"

    echo_url: bool | None = True

settings = Settings()
