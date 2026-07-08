from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class QuoteCategory(StrEnum):
    motivation = "Motivation"
    romance = "Romance"
    sci_fi = "Sci-Fi"


class CreateSummaryRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    author: str | None = Field(default=None, max_length=120)
    cover: str | None = Field(default=None, max_length=16)
    description: str = Field(..., min_length=1, max_length=5000)
    contributor: str | None = Field(default=None, max_length=80)

    @field_validator("title", "description")
    @classmethod
    def _trim(cls, v: str) -> str:
        return v.strip()
