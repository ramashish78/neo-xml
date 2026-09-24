from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    host: str = "0.0.0.0"
    port: int = 8017
    mongodb_uri: str
    mongo_db: str = "neo_xml"
    jwt_secret: str
    jwt_access_minutes: int = 15
    jwt_refresh_days: int = 7
    upload_root: str = "var/uploads"
    max_upload_bytes: int = 50 * 1024 * 1024
    cors_origins: str = "http://localhost:8017"
    admin_email: str = "admin@neo-xml.local"
    admin_password: str = "ChangeMe123!"
    admin_name: str = "Neo Admin"

    @field_validator("mongodb_uri")
    @classmethod
    def mongo_required(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("MONGODB_URI is required")
        return value.strip()

    @field_validator("jwt_secret")
    @classmethod
    def secret_required(cls, value: str) -> str:
        if not value or len(value.strip()) < 16:
            raise ValueError("JWT_SECRET is required and must be at least 16 characters")
        return value.strip()

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
