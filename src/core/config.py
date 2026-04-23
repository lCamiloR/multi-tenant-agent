from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    primary_jwt_secret_key: str
    previous_jwt_secret_key: Optional[str] = None
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    anthropic_api_key: str

    class Config:
        env_file = ".env"

SETTINGS = Settings()  # Falha no startup se JWT_SECRET_KEY não existir