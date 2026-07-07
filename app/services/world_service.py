from app.core.exceptions import ForbiddenError
from app.db.container import get_repositories

STAGES = [
    {"stage": 0, "threshold": 0, "label": "Full black & white"},
    {"stage": 1, "threshold": 5, "label": "Grass turns green"},
    {"stage": 2, "threshold": 15, "label": "Flowers begin to bloom"},
    {"stage": 3, "threshold": 30, "label": "Trees gain color"},
    {"stage": 4, "threshold": 50, "label": "Birds, butterflies & rivers appear"},
    {"stage": 5, "threshold": 100, "label": "Full-color living forest"},
]

_LAYERS = {
    0: ["forest-base-bw.png"],
    1: ["forest-base-bw.png", "forest-grass.png"],
    2: ["forest-base-bw.png", "forest-grass.png", "forest-flowers.png"],
    3: ["forest-base-bw.png", "forest-grass.png", "forest-flowers.png", "forest-trees.png"],
    4: [
        "forest-base-bw.png",
        "forest-grass.png",
        "forest-flowers.png",
        "forest-trees.png",
        "forest-birds.png",
        "forest-river.png",
    ],
    5: [
        "forest-base-bw.png",
        "forest-grass.png",
        "forest-flowers.png",
        "forest-trees.png",
        "forest-birds.png",
        "forest-river.png",
        "forest-full.png",
    ],
}


def get_world(user_id: str) -> dict:
    repos = get_repositories()
    user = repos.users.get_by_id(user_id)
    if not user["is_premium"]:
        raise ForbiddenError(
            "World Comes to Life is a premium feature", {"is_premium": False}
        )

    books_completed = user["books_completed"]
    stage = user["world_stage"]
    current = STAGES[stage]
    nxt = STAGES[stage + 1] if stage + 1 < len(STAGES) else None

    progress_to_next = 1.0
    books_to_next_stage = None
    next_threshold = None
    if nxt:
        span = nxt["threshold"] - current["threshold"]
        progress_to_next = (
            round((books_completed - current["threshold"]) / span, 4) if span else 1.0
        )
        books_to_next_stage = nxt["threshold"] - books_completed
        next_threshold = nxt["threshold"]

    return {
        "is_premium": True,
        "books_completed": books_completed,
        "world_stage": stage,
        "stage_label": current["label"],
        "current_threshold": current["threshold"],
        "next_threshold": next_threshold,
        "books_to_next_stage": books_to_next_stage,
        "progress_to_next": progress_to_next,
        "layers": _LAYERS[stage],
        "stages": STAGES,
    }
