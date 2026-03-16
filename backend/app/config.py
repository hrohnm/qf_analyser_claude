from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Look for .env in current dir, then one level up (project root)
    model_config = SettingsConfigDict(
        env_file=[".env", "../.env"],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_football_key: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    database_url: str = "postgresql+asyncpg://qf_user:qf_secret@localhost:5432/qf_analyser"
    database_url_sync: str = "postgresql+psycopg2://qf_user:qf_secret@localhost:5432/qf_analyser"
    environment: str = "development"
    api_daily_limit: int = 7500
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    live_fixture_refresh_enabled: bool = True
    live_fixture_refresh_interval_seconds: int = 300

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


settings = Settings()
