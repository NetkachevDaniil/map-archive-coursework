from functools import lru_cache
from pathlib import Path

from pydantic import EmailStr
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "OrientMaps"
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    verify_token_expire_minutes: int = 60 * 24

    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/orientmaps"

    first_admin_login: str = "admin"
    first_admin_email: EmailStr = "car_specific@mail.ru"
    first_admin_password: str = "change-me"
    omaps_spb_login: str = "o-maps.spb.ru"
    omaps_spb_password: str = "change-me"
    omaps_moscow_login: str = "o-maps.moscow.ru"
    omaps_moscow_password: str = "change-me"

    cookie_secure: bool = False
    expose_local_media: bool = False

    max_upload_bytes: int = 50 * 1024 * 1024
    parser_min_year: int = 2020

    rate_limit_enabled: bool = True
    rate_limit_window_seconds: int = 60
    rate_limit_max_requests: int = 120
    rate_limit_post_window_seconds: int = 60
    rate_limit_max_post_requests: int = 25
    rate_limit_block_seconds: int = 300

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_sender: EmailStr = "noreply@o-maps.net.ru"
    smtp_use_ssl: bool = False
    smtp_use_tls: bool = True
    smtp_timeout_seconds: int = 20

    use_s3: bool = False
    s3_endpoint_url: str | None = "https://storage.yandexcloud.net"
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_bucket_name: str | None = None
    s3_region: str | None = "ru-central1"
    s3_public_base_url: str | None = None

    local_upload_dir: str = str(BASE_DIR / "uploads")
    site_background_url: str = "https://storage.yandexcloud.net/orientmaps-archive/ui/site-background.jpg"
    default_avatar_url: str = "https://i.pinimg.com/736x/bf/3a/5b/bf3a5beed53640cb39c307219a7d1837.jpg"

    parser_user_agent: str = "OrientMapsBot/1.0 (+coursework parser)"


@lru_cache
def get_settings() -> Settings:
    return Settings()
