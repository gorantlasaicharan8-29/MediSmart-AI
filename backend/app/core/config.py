from pathlib import Path
from typing import List, Optional
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent

# Known development fallback secrets that must never be permitted in production
KNOWN_DEV_SECRETS = {
    "dev-secret-change-in-production-random-bytes-key-32chars",
}


class Settings(BaseSettings):
    PROJECT_NAME: str = "MediSmart API"
    VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"
    
    # Environment & Deployment Mode
    ENVIRONMENT: str = "development"
    
    # Database (loaded from backend/.env)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/medismart_db"
    
    # Security & Tokens
    SECRET_KEY: str = "dev-secret-change-in-production-random-bytes-key-32chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_ISSUER: str = "medismart"
    
    # Cookie Security: None resolves to True in production, False otherwise
    COOKIE_SECURE: Optional[bool] = None

    # Interactive API Documentation (/docs, /redoc, /openapi.json):
    # None resolves to False in production, True otherwise
    DOCS_ENABLED: Optional[bool] = None
    
    # WebSocket Multi-Worker Broadcast Backend: "memory" (single-process dev) | "redis" (multi-worker)
    WS_BROADCAST_BACKEND: str = "memory"
    REDIS_URL: str = "redis://localhost:6379/0"

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key_strength(cls, v: str) -> str:
        if not v or len(v.strip()) < 32:
            raise ValueError(
                "Insecure configuration: SECRET_KEY must be defined and at least 32 characters long."
            )
        return v

    @model_validator(mode="after")
    def validate_environment_and_security(self) -> "Settings":
        env = self.ENVIRONMENT.lower().strip()
        is_prod = env == "production"

        # Resolve defaults if not explicitly configured
        if self.COOKIE_SECURE is None:
            self.COOKIE_SECURE = is_prod

        if self.DOCS_ENABLED is None:
            self.DOCS_ENABLED = not is_prod

        if is_prod:
            # Enforce production secret standards without disclosing secret value in logs/errors
            if self.SECRET_KEY.strip() in KNOWN_DEV_SECRETS or "dev-secret" in self.SECRET_KEY.lower():
                raise ValueError(
                    "Insecure production configuration: SECRET_KEY cannot use the known development fallback secret in production."
                )
            if not self.COOKIE_SECURE:
                raise ValueError(
                    "Insecure production configuration: COOKIE_SECURE cannot be False in production HTTPS environments."
                )

        # Validate WebSocket broadcast backend configuration
        backend = self.WS_BROADCAST_BACKEND.lower().strip()
        if backend not in {"memory", "redis"}:
            raise ValueError(
                "Invalid configuration: WS_BROADCAST_BACKEND must be either 'memory' or 'redis'."
            )
        if backend == "redis" and (not self.REDIS_URL or not self.REDIS_URL.strip()):
            raise ValueError(
                "Invalid configuration: REDIS_URL must be defined when WS_BROADCAST_BACKEND is 'redis'."
            )

        return self

    model_config = SettingsConfigDict(
        env_file=(_BACKEND_DIR / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

