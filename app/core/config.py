from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Payment Gateway API"
    environment: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/payment_gateway"

    # JWT Settings
    jwt_secret_key: str = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Symmetric Encryption Master Key (32-byte url-safe base64-encoded)
    encryption_master_key: str = "xOqjS-O-5eI00BvX8eXw9B8HZb-vH1E9P_M4nU0oR3g="

    # Redis Settings
    redis_url: str = "redis://localhost:6379/0"

    @property
    def DATABASE_URL(self) -> str:
        return self.database_url

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="PAYMENT_GATEWAY_",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
