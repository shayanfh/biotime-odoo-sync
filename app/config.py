from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # BioTime
    biotime_base_url: str
    biotime_username: str
    biotime_password: str
    biotime_auth_type: str = "jwt"

    # Odoo
    odoo_url: str
    odoo_db: str
    odoo_username: str
    odoo_password: str
    odoo_employee_code_field: str = "barcode"

    # Sync
    local_timezone: str = "Asia/Muscat"
    sync_page_size: int = 1000
    sync_start_from: str | None = None
    auto_checkout_time: str = "15:00"

    # Daily job
    daily_sync_hour: int = 22
    daily_sync_minute: int = 0

    # First run
    initial_sync_months: int = 3

    # Database
    database_url: str = "sqlite:///./sync.db"

    # Logging
    log_level: str = "INFO"

    class Config:
        env_file = ".env"


settings = Settings()