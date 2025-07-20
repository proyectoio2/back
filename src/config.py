from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional, Dict, Any, List, Union
from pydantic import PostgresDsn, validator, Field

class Settings(BaseSettings):
    PROJECT_NAME: str = "FastAPI Project"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Database
    POSTGRES_SERVER: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_PORT: str = "5432"

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Email
    SMTP_SERVER: str
    SMTP_PORT: int
    SMTP_USERNAME: str
    SMTP_PASSWORD: str
    SENDER_EMAIL: str
    URL: str

    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30
    PASSWORD_HISTORY_SIZE: int = 5

    DO_SPACES_KEY: str
    DO_SPACES_SECRET: str
    DO_SPACES_ENDPOINT: str
    DO_SPACES_CDN_ENDPOINT: Optional[str] = None
    DO_SPACES_REGION: str
    DO_SPACES_BUCKET: str
    DO_SPACES_MAX_IMAGE_SIZE: int = 10 * 1024 * 1024  # 10MB default limit

    # Configuración de Twilio
    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str
    TWILIO_WHATSAPP_NUMBER: str
    VENDEDOR_WHATSAPP_NUMBER: str

    # Configuración de intentos de inicio de sesión y bloqueo
    MAX_LOGIN_ATTEMPTS: int = 5  # Número máximo de intentos fallidos antes de bloquear
    ACCOUNT_LOCKOUT_MINUTES: int = 15  # Tiempo de bloqueo en minutos

    # Configuración de contraseñas
    MIN_PASSWORD_LENGTH: int = 8

    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings():
    return Settings()