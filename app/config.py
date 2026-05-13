from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    postgres_host: str = "localhost"
    postgres_db: str = "localez"
    postgres_user: str = "localez"
    postgres_password: SecretStr = "change-me"
    postgres_port: int = 5432
    secret_key: SecretStr = "change-me"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    webauthn_rp_id: str = "localhost"
    webauthn_rp_name: str = "Localez"
    webauthn_origin: str = "http://localhost:8000"
    recovery_word_list_path: str = "app/core/wordlist.txt"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
