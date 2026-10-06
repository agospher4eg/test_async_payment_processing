from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Postgres
    POSTGRES_USER: str = "payments"
    POSTGRES_PASSWORD: str = "payments"
    POSTGRES_DB: str = "payments"
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432

    API_KEY: str
    APP_NAME: str = "payments-app"
    
    RABBITMQ_USER: str = "guest"
    RABBITMQ_PASSWORD: str = "guest"
    RABBITMQ_HOST: str = "rabbitmq"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_VHOST: str = "/"

    PAYMENT_SUCCESS_RATE: float = 0.9
    PAYMENT_MIN_DELAY_SEC: int = 2
    PAYMENT_MAX_DELAY_SEC: int = 5
    PAYMENT_MAX_ATTEMPTS: int =3
    PAYMENT_RETRY_TTL_MS: int = 10000

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def rabbitmq_url(self) -> str:
        vhost = self.RABBITMQ_VHOST.lstrip("/")
        return (
            f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASSWORD}"
            f"@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}/{vhost}"
        )
    
settings = Settings()