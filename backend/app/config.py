from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração da API, carregada de variáveis de ambiente / `.env`."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ambiente: str = "dev"
    database_url: str = "postgresql+asyncpg://ritmo:ritmo@localhost:5432/ritmo"
    cors_origens: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    sql_echo: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
