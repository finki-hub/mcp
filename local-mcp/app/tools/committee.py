import logging

import httpx

from app.schemas.committee import CommitteeRecommendation
from app.utils.settings import Settings

logger = logging.getLogger(__name__)

_settings = Settings()
_TIMEOUT = 60.0
_ERROR_MESSAGE = (
    "Сервисот за препорака на комисии за дипломски работи моментално е недостапен."
)


async def recommend_committee(
    title: str,
    mentor: str | None = None,
) -> CommitteeRecommendation:
    url = f"{_settings.CHAT_BOT_API_URL.rstrip('/')}/recommendations/"
    payload: dict[str, object] = {"title": title}
    if mentor:
        payload["mentor"] = mentor

    mode = "members_only" if mentor else "full"

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError, ValueError:
        logger.exception("Committee recommendation request failed")
        return CommitteeRecommendation(
            mode=mode,
            mentor=mentor,
            members=[],
            error=_ERROR_MESSAGE,
        )

    if not isinstance(data, dict):
        logger.error("Unexpected recommendation payload type: %s", type(data).__name__)
        return CommitteeRecommendation(
            mode=mode,
            mentor=mentor,
            members=[],
            error=_ERROR_MESSAGE,
        )

    mentor_obj = data.get("mentor")
    recommended_mentor = (
        mentor_obj.get("name") if isinstance(mentor_obj, dict) else None
    )

    members_raw = data.get("members")
    members = (
        [m["name"] for m in members_raw if isinstance(m, dict) and m.get("name")]
        if isinstance(members_raw, list)
        else []
    )

    return CommitteeRecommendation(
        mode=str(data.get("mode") or mode),
        mentor=mentor or recommended_mentor,
        members=members,
    )
