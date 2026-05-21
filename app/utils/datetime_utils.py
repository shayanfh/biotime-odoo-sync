from datetime import datetime
from zoneinfo import ZoneInfo


def local_to_utc_string(value: str, local_timezone: str) -> str:
    local_tz = ZoneInfo(local_timezone)
    utc_tz = ZoneInfo("UTC")
    dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    local_dt = dt.replace(tzinfo=local_tz)
    return local_dt.astimezone(utc_tz).strftime("%Y-%m-%d %H:%M:%S")


def utc_now_string() -> str:
    return datetime.now(ZoneInfo("UTC")).strftime("%Y-%m-%d %H:%M:%S")


def local_now_string(local_timezone: str) -> str:
    return datetime.now(ZoneInfo(local_timezone)).strftime("%Y-%m-%d %H:%M:%S")
