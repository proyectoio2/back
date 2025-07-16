from datetime import datetime, UTC, timedelta

def get_utc_now() -> datetime:
    return datetime.now(UTC)

def get_future_datetime(days: int = 0, minutes: int = 0) -> datetime:
    return get_utc_now() + timedelta(days=days, minutes=minutes)
