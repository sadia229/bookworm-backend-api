import re
from datetime import UTC, date, datetime
from enum import StrEnum


class Gender(StrEnum):
    male = "male"
    female = "female"
    other = "other"
    prefer_not_to_say = "prefer_not_to_say"


class Genre(StrEnum):
    fiction = "fiction"
    nonfiction = "nonfiction"
    sci_fi = "sci-fi"
    fantasy = "fantasy"
    mystery = "mystery"
    thriller = "thriller"
    romance = "romance"
    poetry = "poetry"
    biography = "biography"
    history = "history"
    self_help = "self-help"
    other = "other"


class BookStatus(StrEnum):
    currently_reading = "currently_reading"
    already_read = "already_read"


class NotificationPlatform(StrEnum):
    android = "android"
    ios = "ios"
    web = "web"


class LeaderboardPeriod(StrEnum):
    all_time = "all_time"
    weekly = "weekly"


_PASSWORD_RE = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{8,128}$")
_REMINDER_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def validate_reminder_time(value: str) -> str:
    if not _REMINDER_TIME_RE.match(value):
        raise ValueError("reminder_time must be HH:mm in 24-hour format")
    return value


def validate_password_strength(password: str) -> str:
    if not _PASSWORD_RE.match(password):
        raise ValueError("Password must be at least 8 characters and contain a letter and a digit")
    return password


def validate_dob(value: date) -> date:
    today = datetime.now(UTC).date()
    if value > today:
        raise ValueError("dob cannot be in the future")
    age_days = (today - value).days
    if age_days < 5 * 365:
        raise ValueError("dob implies an age below the minimum of 5 years")
    return value


def validate_not_future(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    if value > datetime.now(UTC):
        raise ValueError("timestamp cannot be in the future")
    return value
