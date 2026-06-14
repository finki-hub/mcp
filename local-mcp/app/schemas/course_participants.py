from pydantic import BaseModel, ConfigDict, Field


class ParticipantsData(BaseModel):
    course: str = Field(
        ...,
        description="The name of the course",
        examples=["Архитектура и организација на компјутери"],
    )
    error: str | None = Field(
        None,
        description="Error message if the course is not found",
        examples=["Course not found"],
    )
    suggestions: list[str] | None = Field(
        None,
        description="Suggested course names if no exact match is found",
    )
    match_info: dict | None = Field(
        None,
        description="Metadata about the matching process",
    )

    model_config = ConfigDict(extra="allow")
