import logging

import httpx

from app.schemas.committee import CommitteeRecommendation
from app.utils.settings import Settings

logger = logging.getLogger(__name__)

_settings = Settings()
_TIMEOUT = 60.0


async def recommend_committee(
    title: str,
    mentor: str | None = None,
) -> CommitteeRecommendation:
    url = f"{_settings.CHAT_BOT_API_URL.rstrip('/')}/recommendations/"
    payload: dict[str, object] = {"title": title}
    if mentor:
        payload["mentor"] = mentor

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        logger.exception("Committee recommendation request failed")
        return CommitteeRecommendation(
            mode="members_only" if mentor else "full",
            mentor=mentor,
            members=[],
            error=f"Recommendation service error: {exc}",
        )

    recommended_mentor = data.get("mentor") or {}
    return CommitteeRecommendation(
        mode=data.get("mode", ""),
        mentor=recommended_mentor.get("name") or None,
        members=[member["name"] for member in data.get("members", [])],
    )
