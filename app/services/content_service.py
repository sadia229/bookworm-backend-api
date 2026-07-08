from app.core.envelope import paginated
from app.db.container import get_repositories


def _serialize_quote(row: dict) -> dict:
    return {
        "id": row["id"],
        "text": row["text"],
        "author": row.get("author"),
        "category": row.get("category"),
    }


def _serialize_summary(row: dict) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "author": row.get("author"),
        "cover": row.get("cover"),
        "description": row["description"],
        "contributor": row.get("contributor", "Editor"),
    }


def get_quotes(category: str | None, limit: int) -> list[dict]:
    repos = get_repositories()
    rows = repos.content.list_quotes(category, limit)
    return [_serialize_quote(r) for r in rows]


def get_summaries(page: int, size: int) -> dict:
    repos = get_repositories()
    rows, total = repos.content.list_summaries(page, size)
    return paginated([_serialize_summary(r) for r in rows], page, size, total)
