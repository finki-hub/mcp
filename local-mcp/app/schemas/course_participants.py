from pydantic import BaseModel, ConfigDict, Field


class ParticipantsData(BaseModel):
    course: str = Field(
        ...,
        description="Името на предметот",
        examples=["Архитектура и организација на компјутери"],
    )
    error: str | None = Field(
        None,
        description="Порака за грешка доколку предметот не е пронајден",
        examples=["Course not found"],
    )
    suggestions: list[str] | None = Field(
        None,
        description="Предложени имиња на предмети доколку нема точно совпаѓање",
    )
    match_info: dict | None = Field(
        None,
        description="Метаподатоци за процесот на совпаѓање",
    )

    model_config = ConfigDict(extra="allow")
