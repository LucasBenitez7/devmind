from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    environment: str = "development"
    secret_key: str = "changeme-in-production"
    log_level: str = "INFO"
    version: str = "0.1.0"

    # Database
    database_url: str = "postgresql+asyncpg://devmind:devmind@localhost:5432/devmind"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth0
    auth0_domain: str = ""
    auth0_audience: str = ""
    auth0_client_id: str = ""

    # LLM
    anthropic_api_key: str = ""

    # Embeddings
    openai_api_key: str = ""

    # Web Search
    tavily_api_key: str = ""

    # Re-ranking
    cohere_api_key: str = ""

    # Storage (Cloudflare R2)
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = "devmind-docs"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Sentry
    sentry_dsn: str = ""


settings = Settings()
