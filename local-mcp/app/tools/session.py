from app.schemas.session import (
    ExamSessionScheduleFile,
    ExamSessionScheduleFiles,
)
from app.utils.http_client import get_exam_sessions
from app.utils.settings import Settings

_settings = Settings()


def list_exam_session_schedules() -> ExamSessionScheduleFiles:
    base_url = f"{_settings.DATA_STORAGE_URL.rstrip('/')}/sessions/"
    return ExamSessionScheduleFiles(
        base_url=base_url,
        files=[
            ExamSessionScheduleFile(session=session, filename=filename)
            for session, filename in get_exam_sessions().items()
        ],
    )
