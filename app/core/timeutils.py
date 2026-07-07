from datetime import UTC, datetime


def parse_dt(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def iso(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    return parse_dt(value).isoformat().replace("+00:00", "Z")
