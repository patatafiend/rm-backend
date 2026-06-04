from datetime import datetime, timezone

def as_utc(dt: datetime) -> datetime:
    """Treat a naive datetime from MySQL as UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt