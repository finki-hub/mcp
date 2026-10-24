from app.schemas.base import ListPage


def paginate[Item](items: list[Item], *, limit: int, offset: int = 0) -> ListPage[Item]:
    page = items[offset : offset + limit]
    truncated = offset + len(page) < len(items)
    note = None
    if truncated:
        note = (
            f"Прикажани се {len(page)} од {len(items)} резултати (offset {offset}). "
            "Стеснете го барањето со филтри или повикајте повторно со "
            f"`offset`={offset + len(page)} за следните."
        )
    return ListPage[Item](total=len(items), truncated=truncated, note=note, items=page)
