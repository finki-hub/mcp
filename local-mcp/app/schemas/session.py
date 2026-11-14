from pydantic import BaseModel, Field


class ExamSessionScheduleFile(BaseModel):
    session: str = Field(
        ...,
        description="Ознака на испитната сесија.",
        examples=["2025/2026 Јуни"],
    )
    download_url: str = Field(
        ...,
        description="Линк за преземање на распоредот.",
        examples=["https://data.finki-hub.com/legacy/sessions/jun_2025_2026.xlsx"],
    )
