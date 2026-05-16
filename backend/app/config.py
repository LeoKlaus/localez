import os

from pydantic import SecretStr, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_WEAK_SECRET_KEYS = {"change-me-to-a-long-random-string"}
_WEAK_POSTGRES_PASSWORDS = {"localez", "postgres", "password", "changeme"}


class Settings(BaseSettings):
    allowed_hosts: str = "*"
    postgres_host: str = "db"
    postgres_db: str = "localez"
    postgres_user: str = "localez"
    postgres_password: SecretStr
    postgres_port: int = 5432
    secret_key: SecretStr
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    webauthn_rp_id: str = "localhost"
    webauthn_rp_name: str = "Localez"
    webauthn_origin: str = "http://localhost:8000"
    recovery_word_list_path: str = "app/core/wordlist.txt"
    deepl_api_key: SecretStr | None = None
    deepl_api_base: str = "https://api-free.deepl.com/v2"
    llm_api_key: SecretStr | None = None
    llm_api_base: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"

    @field_validator("secret_key", mode="before")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if os.getenv("TESTING"):
            return v
        raw = v.get_secret_value() if isinstance(v, SecretStr) else v
        if raw in _WEAK_SECRET_KEYS:
            raise ValueError("SECRET_KEY is set to the example default — replace it with a strong random value")
        if len(raw) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        return v

    @field_validator("postgres_password", mode="before")
    @classmethod
    def validate_postgres_password(cls, v: str) -> str:
        if os.getenv("TESTING"):
            return v
        raw = v.get_secret_value() if isinstance(v, SecretStr) else v
        if raw in _WEAK_POSTGRES_PASSWORDS:
            raise ValueError(f"POSTGRES_PASSWORD '{raw}' is a known weak default — use a strong password")
        if len(raw) < 12:
            raise ValueError("POSTGRES_PASSWORD must be at least 12 characters")
        return v

    @computed_field
    @property
    def prefill_provider(self) -> str | None:
        if self.llm_api_key:
            return "llm"
        if self.deepl_api_key:
            return "deepl"
        return None

    model_config = SettingsConfigDict(
        env_file=None if os.getenv("TESTING") else "../.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
