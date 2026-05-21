from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # BioTime
    biotime_base_url: str
    biotime_username: str
    biotime_password: str
    biotime_auth_type: str = "jwt"  # jwt or token

    # Odoo
    odoo_url: str
    odoo_db: str
    odoo_username: str
    odoo_password: str
    odoo_employee_code_field: str = "barcode"

    # Sync
    local_timezone: str = "Asia/Muscat"
    sync_interval_minutes: int = 5
    sync_page_size: int = 1000
    sync_start_from: str | None = None

    # Database
    database_url: str = "sqlite:///./sync.db"

    class Config:
        env_file = ".env"


settings = Settings()
