from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    APP_NAME: str = "ERP SYSTEM"

    DEBUG: bool = True

    SECRET_KEY: str

    ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    DB_HOST: str
    DB_PORT: int
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str


    class Config:
        env_file = ".env"


settings = Settings()
