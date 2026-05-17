from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    primary_jwt_secret_key: str
    previous_jwt_secret_key: Optional[str] = None
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    anthropic_api_key: str

    # --- Milvus ---
    # Em desenvolvimento: "./licitacoes.db" (Milvus Lite, sem Docker)
    # Em produção:        "http://milvus:19530" (Milvus standalone via Docker Compose)
    milvus_uri: str = "./licitacoes.db"

    # --- Temporal ---
    # Endereço do servidor Temporal.
    # Em desenvolvimento: "localhost:7233"
    # Em produção via Docker Compose: "temporal:7233"
    temporal_host: str = "localhost:7233"

    # --- Postgres ---
    # URL de conexão SQLAlchemy. Exemplos:
    #   postgresql+asyncpg://user:password@localhost:5432/multi_tenant_agent
    database_url: str = "postgresql+asyncpg://postgres:secret@localhost:5432/multi_tenant_agent"

    class Config:
        env_file = ".env"
        extra = "ignore"

SETTINGS = Settings()  # Falha no startup se JWT_SECRET_KEY não existir