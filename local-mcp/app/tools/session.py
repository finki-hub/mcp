from app.schemas.base import ListPage
from app.schemas.session import ExamSessionScheduleFile
from app.utils.http_client import get_exam_sessions
from app.utils.pagination import paginate
from app.utils.query_matcher import transliterate_and_normalize
from app.utils.settings import Settings

DEFAULT_SESSION_LIMIT = 10

_settings = Settings()


def list_exam_session_schedules(
    *,
    academic_year: str | None = None,
    query: str | None = None,
    limit: int = DEFAULT_SESSION_LIMIT,
    offset: int = 0,
) -> ListPage[ExamSessionScheduleFile]:
    base_url = f"{_settings.DATA_STORAGE_URL.rstrip('/')}/sessions/"
    normalized_query = transliterate_and_normalize(query) if query else ""
    files = [
        ExamSessionScheduleFile(session=session, download_url=f"{base_url}{filename}")
        for session, filename in get_exam_sessions().items()
        if (academic_year is None or session.startswith(academic_year.strip()))
        and (
            not normalized_query
            or normalized_query in transliterate_and_normalize(session)
        )
    ]
    return paginate(files, limit=limit, offset=offset)
