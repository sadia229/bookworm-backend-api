from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.core.timeutils import iso
from app.db.container import get_repositories


def create_bookmark(user_id: str, book_id: str) -> dict:
    repos = get_repositories()
    book = repos.books.get_by_id(book_id)
    if not book or book["status"] != "already_read":
        raise NotFoundError("Book not found")
    if book["user_id"] == user_id:
        raise BadRequestError("You can't bookmark your own book")
    if repos.bookmarks.exists(user_id, book_id):
        raise ConflictError("You already bookmarked this book")

    bookmark = repos.bookmarks.create(user_id, book_id)
    return {
        "id": bookmark["id"],
        "book_id": bookmark["book_id"],
        "owner_id": book["user_id"],
        "created_at": iso(bookmark["created_at"]),
    }


def list_bookmarks(user_id: str, page: int, size: int) -> tuple[list[dict], int]:
    repos = get_repositories()
    items, total = repos.bookmarks.list_by_user(user_id, page, size)

    book_ids = [b["book_id"] for b in items]
    books = repos.books.get_many_by_ids(book_ids)
    owner_ids = [b["user_id"] for b in books.values()]
    owners = repos.users.get_many_by_ids(owner_ids)

    serialized = []
    for row in items:
        book = books.get(row["book_id"])
        if not book:
            continue
        owner = owners.get(book["user_id"])
        if not owner:
            continue
        serialized.append(
            {
                "id": row["id"],
                "created_at": iso(row["created_at"]),
                "owner": {
                    "id": owner["id"],
                    "display_name": (
                        "Anonymous Reader" if owner["name_hidden"] else owner["display_name"]
                    ),
                    "avatar_id": owner.get("avatar_id"),
                },
                "book": {
                    "id": book["id"],
                    "title": book["title"],
                    "author": book["author"],
                    "genre": book.get("genre"),
                    "cover_url": book.get("cover_url"),
                    "rating": book.get("rating"),
                    "summary": book.get("summary"),
                },
            }
        )
    return serialized, total


def delete_bookmark(user_id: str, bookmark_id: str) -> None:
    repos = get_repositories()
    bookmark = repos.bookmarks.get_by_id(bookmark_id)
    if not bookmark:
        raise NotFoundError("Bookmark not found")
    if bookmark["user_id"] != user_id:
        raise ForbiddenError("You do not have access to this bookmark")
    repos.bookmarks.delete(bookmark_id)


def delete_bookmark_by_book(user_id: str, book_id: str) -> None:
    repos = get_repositories()
    if not repos.bookmarks.delete_by_book(user_id, book_id):
        raise NotFoundError("Bookmark not found")
