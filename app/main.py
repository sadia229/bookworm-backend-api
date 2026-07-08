import logging

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.core.envelope import failure, success
from app.core.exceptions import AppError
from app.routers import (
    auth,
    bookmarks,
    books,
    content,
    cron,
    leaderboard,
    notifications,
    premium,
    progress,
    reviews,
    stats,
    users,
    world,
)

logger = logging.getLogger("bookworm")

app = FastAPI(title="Book-Worm API", version="1.0.0")

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_v1 = APIRouter(prefix="/api/v1")
for router in (
    auth.router,
    users.router,
    books.router,
    progress.router,
    reviews.router,
    world.router,
    bookmarks.router,
    leaderboard.router,
    stats.router,
    notifications.router,
    premium.router,
    content.router,
    cron.router,
):
    api_v1.include_router(router)

app.include_router(api_v1)


@app.get("/")
@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse(status_code=200, content=success({"status": "ok"}, "Book-Worm API"))


@app.on_event("startup")
def on_startup() -> None:
    try:
        from app.db.supabase_client import ensure_storage_buckets

        ensure_storage_buckets()
    except Exception:
        logger.warning(
            "Could not verify/create Supabase storage buckets at startup", exc_info=True
        )


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=failure(exc.message, exc.data))


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    field_errors: dict[str, str] = {}
    for error in errors:
        loc = error.get("loc", ())
        field = str(loc[-1]) if loc else "body"
        field_errors[field] = error.get("msg", "invalid")

    if errors:
        first = errors[0]
        field = str(first["loc"][-1]) if first.get("loc") else "body"
        message = f"{field}: {first.get('msg', 'invalid')}"
    else:
        message = "Invalid request"

    return JSONResponse(status_code=422, content=failure(message, {"errors": field_errors}))


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error")
    return JSONResponse(
        status_code=500, content=failure("Something went wrong. Please try again.")
    )
