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
    # chat-bot API, reachable by service name on the shared docker network.
    CHAT_BOT_API_URL: str = "http://api:8880"
