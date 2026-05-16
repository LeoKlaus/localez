from pydantic import SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
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

    @computed_field
    @property
    def prefill_provider(self) -> str | None:
        if self.llm_api_key:
            return "llm"
        if self.deepl_api_key:
            return "deepl"
        return None

    model_config = SettingsConfigDict(env_file="../.env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
