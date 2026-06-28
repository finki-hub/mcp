from pydantic import BaseModel, Field


class ExamSessionScheduleFile(BaseModel):
    session: str = Field(
        ...,
        description="Ознака на испитната сесија.",
        examples=["2025/2026 Јуни"],
    )
    filename: str = Field(
        ...,
        description="Име на датотеката во директориумот за преземање распореди.",
        examples=["jun_2025_2026.xlsx"],
    )


class ExamSessionScheduleFiles(BaseModel):
    base_url: str = Field(
        ...,
        description=("Основен линк за преземање датотеки на распореди."),
        examples=["https://assets.finki-hub.com/sessions/"],
    )
    files: list[ExamSessionScheduleFile] = Field(
        default_factory=list,
        description="Достапни датотеки со распореди за испитни сесии.",
    )
