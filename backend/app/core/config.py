from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All settings come from environment variables / .env (see .env.example)."""

    # Reads backend/.env first, then the repo-root .env when running from backend/.
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    database_url: str = "postgresql+psycopg://koyla:koyla@localhost:5432/koyla"
    redis_url: str = "redis://localhost:6379/0"
    storage_dir: str = "./storage"
    max_upload_mb: int = 100

    llm_base_url: str = "http://localhost:11434"
    llm_model: str = "qwen2.5:3b-instruct"  # same as .env.example; 7B on GPU / 16 GB+ machines
    embed_model: str = "bge-m3"
    llm_num_ctx: int = 8192  # context window; must fit the prompt + ~6 passages
    ocr_engine: str = "paddle"
    # Ask the local LLM to name a table's metric when the keyword rules find none (guide 7.2).
    extract_use_llm: bool = True
    allow_external_calls: bool = False
    # Re-build the topics (guide 11) once this many new PQs have arrived since the last run.
    topics_min_new_pqs: int = 5

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 7
    cors_origins: str = "http://localhost:3000"

    seed_demo_password: str = "change-me-too"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
