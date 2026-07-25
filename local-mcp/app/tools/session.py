from app.schemas.session import ExamSessionScheduleFile
from app.utils.http_client import get_exam_sessions
from app.utils.settings import Settings

_settings = Settings()


def list_exam_session_schedules() -> list[ExamSessionScheduleFile]:
    base_url = f"{_settings.DATA_STORAGE_URL.rstrip('/')}/sessions/"
    return [
        ExamSessionScheduleFile(session=session, download_url=f"{base_url}{filename}")
        for session, filename in get_exam_sessions().items()
    ]
