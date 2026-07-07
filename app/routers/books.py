from fastapi import APIRouter, Depends, Query, UploadFile
from fastapi.responses import JSONResponse

from app.core.envelope import paginated, success
from app.deps import get_current_user_id
from app.models.books import BookListQuery, CreateBookRequest, FinishBookRequest, UpdateBookRequest
from app.models.common import BookStatus, Genre
from app.services import book_service

router = APIRouter(tags=["Books"])


@router.post("/books")
def create_book(
    payload: CreateBookRequest, user_id: str = Depends(get_current_user_id)
) -> JSONResponse:
    data = book_service.create_book(user_id, payload)
    return JSONResponse(status_code=201, content=success(data, "Book added to your library"))


@router.get("/books")
def list_books(
    status: BookStatus | None = None,
    q: str | None = None,
    genre: Genre | None = None,
    sort: str = "-updated_at",
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    query = BookListQuery(status=status, q=q, genre=genre, sort=sort, page=page, size=size)
    items, total = book_service.list_books(user_id, query)
    return JSONResponse(
        status_code=200,
        content=success(paginated(items, page, size, total), "Books retrieved"),
    )


@router.get("/books/{book_id}")
def get_book(book_id: str, user_id: str = Depends(get_current_user_id)) -> JSONResponse:
    data = book_service.get_book(user_id, book_id)
    return JSONResponse(status_code=200, content=success(data, "Book retrieved"))


@router.patch("/books/{book_id}")
def update_book(
    book_id: str, payload: UpdateBookRequest, user_id: str = Depends(get_current_user_id)
) -> JSONResponse:
    data = book_service.update_book(user_id, book_id, payload)
    return JSONResponse(status_code=200, content=success(data, "Book updated"))


@router.delete("/books/{book_id}")
def delete_book(book_id: str, user_id: str = Depends(get_current_user_id)) -> JSONResponse:
    book_service.delete_book(user_id, book_id)
    return JSONResponse(status_code=200, content=success({}, "Book deleted"))


@router.post("/books/{book_id}/cover")
async def upload_cover(
    book_id: str, file: UploadFile, user_id: str = Depends(get_current_user_id)
) -> JSONResponse:
    content = await file.read()
    data = book_service.upload_cover(user_id, book_id, content, file.content_type or "")
    return JSONResponse(status_code=201, content=success(data, "Cover uploaded"))


@router.post("/books/{book_id}/finish")
def finish_book(
    book_id: str, payload: FinishBookRequest, user_id: str = Depends(get_current_user_id)
) -> JSONResponse:
    data = book_service.finish_book(user_id, book_id, payload)
    return JSONResponse(
        status_code=200, content=success(data, "Book finished — your world just grew")
    )


@router.get("/users/{user_id}/books")
def list_user_books(
    user_id: str,
    sort: str = "-finished_at",
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    viewer_id: str = Depends(get_current_user_id),
) -> JSONResponse:
    items, total = book_service.list_public_finished(viewer_id, user_id, sort, page, size)
    return JSONResponse(
        status_code=200,
        content=success(paginated(items, page, size, total), "Reader's books retrieved"),
    )
