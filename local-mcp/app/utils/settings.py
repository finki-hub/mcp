from pydantic import SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings.
    """

    APP_TITLE: str = "MCP"
    APP_DESCRIPTION: str = "API providing external context via MCP"
    API_VERSION: str = "1.0.0"

    HOST: str = "0.0.0.0"  # noqa: S104
    PORT: int = 8808

    DATA_STORAGE_URL: str = "https://assets.finki-hub.com"
    DIPLOMAS_API_URL: str = "https://bachelors-api.finki-hub.com/diplomas"
    MASTERS_API_URL: str = "https://masters-api.finki-hub.com/masters"
    TIMETABLES_API_URL: str = "https://timetables-api.finki-hub.com"
    FINKI_ANNOUNCEMENTS_API_URL: str = (
        "https://finki.ukim.mk/wp-json/wp/v2/announcement"
    )
    CHAT_BOT_API_URL: str = "http://api:8880"
    PUBAPI_URL: str = "https://pubapi.finki.ukim.mk"
    PUBAPI_API_KEY: SecretStr = SecretStr("")

    POSTHOG_KEY: str = ""
    POSTHOG_HOST: str = "https://eu.i.posthog.com"
