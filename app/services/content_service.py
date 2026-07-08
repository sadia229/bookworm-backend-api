from app.core.envelope import paginated
from app.db.container import get_repositories
from app.services import notification_service


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


def create_summary(fields: dict) -> dict:
    """Admin: insert a summary, then notify every user that new content is live."""
    repos = get_repositories()
    summary = repos.content.create_summary(fields)
    by = f" by {summary['author']}" if summary.get("author") else ""
    notification_service.notify_users(
        repos.users.list_all_ids(),
        title="New summary added",
        body=f"“{summary['title']}”{by} is now in the Summary tab.",
        data={"type": "new_summary", "summary_id": str(summary["id"])},
    )
    return _serialize_summary(summary)
