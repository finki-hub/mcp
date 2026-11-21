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
        examples=[
            "https://data.finki-hub.com/assets/e74eefcc-caca-4075-9bed-2a03f6dcfe5b/jun_2025_2026.xlsx"
        ],
    )
