from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    primary_jwt_secret_key: str
    previous_jwt_secret_key: Optional[str] = None
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    anthropic_api_key: str
    openai_api_key: str

    milvus_uri: str = "http://localhost:19530"

    # --- Temporal ---
    # Temporal server address.
    # In development: "localhost:7233"
    # In production via Docker Compose: "temporal:7233"
    temporal_host: str = "localhost:7233"

    # --- Postgres ---
    # SQLAlchemy connection URL. Examples:
    #   postgresql+asyncpg://user:password@localhost:5432/multi_tenant_agent
    database_url: str = "postgresql+asyncpg://postgres:secret@localhost:5432/multi_tenant_agent"

    class Config:
        env_file = ".env"
        extra = "ignore"

SETTINGS = Settings()  # Fails at startup if JWT_SECRET_KEY does not exist
