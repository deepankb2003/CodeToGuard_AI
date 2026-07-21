"""
Central config, loaded from environment variables / .env.
Import `settings` anywhere you need a config value — never read os.environ directly
elsewhere in the app, so all config stays in one auditable place.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    huggingface_api_key: str = ""
    huggingface_model: str = "Qwen/Qwen2.5-7B-Instruct"
    github_token: str = ""
    github_webhook_secret: str = ""
    database_url: str = "postgresql://codeguardian:codeguardian@localhost:5432/codeguardian"
    chroma_persist_dir: str = ".chroma"
    coding_standards_path: str = "docs/coding_standards.md"
    env: str = "development"
    log_level: str = "INFO"


settings = Settings()
