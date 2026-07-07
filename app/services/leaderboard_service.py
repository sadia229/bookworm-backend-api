from app.db.container import get_repositories


def get_leaderboard(
    user_id: str, period: str, page: int, size: int
) -> tuple[dict, list[dict], int]:
    repos = get_repositories()
    offset = (page - 1) * size
    rows, total = repos.users.list_leaderboard(period, size, offset)

    items = []
    for index, row in enumerate(rows):
        items.append(
            {
                "rank": offset + index + 1,
                "user_id": row["user_id"],
                "display_name": "Anonymous Reader" if row["name_hidden"] else row["display_name"],
                "name_hidden": row["name_hidden"],
                "avatar_id": row.get("avatar_id"),
                "avatar_url": row.get("avatar_url"),
                "books_completed": row["books_completed"],
                "weekly_books": row["weekly_books"],
                "points": row["points"],
                "world_stage": row["world_stage"],
                "is_current_user": row["user_id"] == user_id,
            }
        )

    me = repos.users.get_rank(user_id, period)
    return me, items, total
