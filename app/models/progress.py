from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

from app.models.common import validate_not_future


class LogProgressRequest(BaseModel):
    pages_read: int = Field(..., ge=1, le=5000)
    minutes: int | None = Field(default=None, ge=1, le=1440)
    date: datetime | None = None

    @field_validator("date")
    @classmethod
    def _not_future(cls, v: datetime | None) -> datetime | None:
        return validate_not_future(v) if v else v


class GroupBy(StrEnum):
    day = "day"
    week = "week"
    month = "month"
