from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.core.envelope import success
from app.models.content import QuoteCategory
from app.services import content_service

router = APIRouter(tags=["Content"])


@router.get("/quotes")
def list_quotes(
    category: QuoteCategory | None = None,
    limit: int = Query(default=20, ge=1, le=100),
) -> JSONResponse:
    data = content_service.get_quotes(category.value if category else None, limit)
    return JSONResponse(status_code=200, content=success(data, "Quotes retrieved"))


@router.get("/summaries")
def list_summaries(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=50),
) -> JSONResponse:
    data = content_service.get_summaries(page, size)
    return JSONResponse(status_code=200, content=success(data, "Summaries retrieved"))
