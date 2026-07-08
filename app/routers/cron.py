"""Scheduled endpoints invoked by Vercel Cron (see vercel.json `crons`).

Vercel Cron issues a GET and, when CRON_SECRET is set, includes it as
`Authorization: Bearer <CRON_SECRET>` — enforced by `require_cron`.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.core.envelope import success
from app.deps import require_cron
from app.services import jobs_service

router = APIRouter(prefix="/cron", tags=["Cron"], dependencies=[Depends(require_cron)])


@router.get("/birthday-wishes")
def birthday_wishes() -> JSONResponse:
    data = jobs_service.send_birthday_wishes()
    return JSONResponse(status_code=200, content=success(data, "Birthday wishes sent"))


@router.get("/forest-nudge")
def forest_nudge() -> JSONResponse:
    data = jobs_service.send_forest_nudges()
    return JSONResponse(status_code=200, content=success(data, "Forest nudges sent"))
