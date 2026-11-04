from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

JWT_ALGORITHM = "HS256"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = Field(
        default="employee_management",
        validation_alias="POSTGRES_DB",
    )
    database_user: str = Field(default="", validation_alias="POSTGRES_USER")
    database_password: SecretStr = Field(
        default=SecretStr(""),
        validation_alias="POSTGRES_PASSWORD",
    )
    jwt_secret: SecretStr = Field(validation_alias="JWT_SECRET", min_length=32)
    access_token_expire_minutes: int = Field(
        default=15,
        validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES",
        ge=1,
        le=1440,
    )

    @property
    def database_url(self) -> URL:
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.database_user or None,
            password=self.database_password.get_secret_value() or None,
            host=self.database_host,
            port=self.database_port,
            database=self.database_name,
        )


settings = Settings()
