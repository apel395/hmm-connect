from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    APP_NAME: str = "HMM Connect"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    SECRET_KEY: str = Field(min_length=32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    SESSION_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    DATABASE_URL: str | None = None
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "erp_db"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    DOCUMENT_STORAGE_PATH: Path = Path("./uploads")
    S3_BUCKET: str | None = None
    S3_PREFIX: str = "documents"
    S3_PRESIGNED_URL_EXPIRES_SECONDS: int = Field(default=600, ge=60, le=3600)
    MAX_DOCUMENT_SIZE_MB: int = Field(default=10, gt=0)
    ALLOWED_DOCUMENT_MIME_TYPES: str = (
        "application/pdf,image/jpeg,image/png,"
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,"
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    AWS_REGION: str | None = None
    EXPORT_EC2_INSTANCE_ID: str | None = None
    EXPORT_WORKDIR: str = "/opt/hmm-connect"
    EXPORT_PYTHON_BIN: str = ".venv/bin/python"
    EXPORT_COMMAND_TIMEOUT_SECONDS: int = Field(default=900, ge=30, le=3600)
    EXPORT_S3_BUCKET: str | None = None
    EXPORT_S3_PREFIX: str = "exports"
    EXPORT_DOWNLOAD_URL_EXPIRES_SECONDS: int = Field(default=300, ge=60, le=3600)
    EXPORT_TMP_DIR: str = "/tmp/hmm-connect-exports"

    JOURNAL_IMPORT_S3_PREFIX: str = "journal-imports"
    JOURNAL_IMPORT_UPLOAD_URL_EXPIRES_SECONDS: int = Field(default=900, ge=60, le=3600)
    JOURNAL_IMPORT_MAX_SIZE_MB: int = Field(default=25, gt=0, le=100)

    @property
    def allowed_document_mime_types(self) -> set[str]:
        return {
            item.strip().lower()
            for item in self.ALLOWED_DOCUMENT_MIME_TYPES.split(",")
            if item.strip()
        }


settings = Settings()
