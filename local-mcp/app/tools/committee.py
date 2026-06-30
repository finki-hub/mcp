import logging

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.committee import CommitteeOption, CommitteeRecommendation
from app.utils.settings import Settings

logger = logging.getLogger(__name__)

_settings = Settings()
_TIMEOUT = 60.0
_ERROR_MESSAGE = (
    "Сервисот за препорака на комисии за дипломски работи моментално е недостапен."
)
_MAX_COUNT = 5
type JsonValue = (
    str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]
)


class CommitteeRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str
    mentor: str | None = None
    context: str | None = None
    avoid: list[str] = Field(default_factory=list)
    count: int = Field(default=1, ge=1, le=_MAX_COUNT)


def _first_option(
    mode: str,
    mentor: str | None,
    recommendations: list[CommitteeOption],
    error: str | None = None,
) -> CommitteeRecommendation:
    first = recommendations[0] if recommendations else None
    return CommitteeRecommendation(
        mode=mode,
        mentor=first.mentor if first else mentor,
        members=first.members if first else [],
        recommendations=recommendations,
        error=error,
    )


def _string_list(value: JsonValue) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _person_name(value: JsonValue) -> str | None:
    if isinstance(value, str):
        return value or None
    if isinstance(value, dict):
        name = value.get("name")
        return name if isinstance(name, str) and name else None
    return None


def _members(value: JsonValue) -> list[str]:
    if not isinstance(value, list):
        return []
    return [name for item in value if (name := _person_name(item))]


def _evidence(value: JsonValue) -> list[str]:
    if not isinstance(value, dict):
        return []

    evidence: list[str] = []
    similar_diplomas = value.get("similar_diplomas")
    if isinstance(similar_diplomas, list):
        for diploma in similar_diplomas:
            if isinstance(diploma, str) and diploma:
                evidence.append(diploma)
            elif isinstance(diploma, dict):
                title = diploma.get("title")
                if isinstance(title, str) and title:
                    evidence.append(title)

    evidence.extend(_string_list(value.get("supporting_paper_titles")))
    return evidence


def _option(data: dict[str, JsonValue], fallback_mentor: str | None) -> CommitteeOption:
    mentor = _person_name(data.get("mentor")) or fallback_mentor
    confidence = data.get("confidence")
    return CommitteeOption(
        mentor=mentor,
        members=_members(data.get("members")),
        confidence=(
            float(confidence)
            if isinstance(confidence, int | float) and not isinstance(confidence, bool)
            else None
        ),
        reasons=_string_list(data.get("confidence_reasons")),
        evidence=_evidence(data.get("evidence")),
    )


def _recommendations(
    data: dict[str, JsonValue],
    fallback_mentor: str | None,
) -> list[CommitteeOption]:
    selected = _option(data, fallback_mentor)
    recommendations = [selected]
    alternatives = data.get("alternatives")
    if isinstance(alternatives, list):
        recommendations.extend(
            _option(item, fallback_mentor)
            for item in alternatives[1:]
            if isinstance(item, dict)
        )
    return recommendations


def _payload(request: CommitteeRequest) -> dict[str, JsonValue]:
    payload: dict[str, JsonValue] = {
        "title": request.title,
        "alternatives": request.count,
    }
    if request.mentor:
        payload["mentor"] = request.mentor
    if request.context:
        payload["abstract"] = request.context
    if request.avoid:
        excluded: list[JsonValue] = list(request.avoid)
        payload["exclude_professors"] = excluded
    return payload


async def recommend_committee(
    request: CommitteeRequest,
) -> CommitteeRecommendation:
    url = f"{_settings.CHAT_BOT_API_URL.rstrip('/')}/recommendations/"
    mode = "members_only" if request.mentor else "full"

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(url, json=_payload(request))
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError, ValueError:
        logger.exception("Committee recommendation request failed")
        return _first_option(
            mode=mode,
            mentor=request.mentor,
            recommendations=[],
            error=_ERROR_MESSAGE,
        )

    if not isinstance(data, dict):
        logger.error("Unexpected recommendation payload type: %s", type(data).__name__)
        return _first_option(
            mode=mode,
            mentor=request.mentor,
            recommendations=[],
            error=_ERROR_MESSAGE,
        )

    return _first_option(
        mode=str(data.get("mode") or mode),
        mentor=request.mentor,
        recommendations=_recommendations(data, request.mentor),
    )
