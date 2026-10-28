from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]

class Settings(BaseSettings):
    database_url: str = 'postgresql+psycopg://guild:guild@127.0.0.1:54329/guild'
    secret_key: str
    secure_cookie: bool = False
    public_origin: str = 'http://127.0.0.1:8000'
    model_config = SettingsConfigDict(env_file=ROOT / '.env', extra='ignore')

settings = Settings()
