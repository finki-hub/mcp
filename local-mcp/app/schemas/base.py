from pydantic import BaseModel, Field, SerializerFunctionWrapHandler, model_serializer


class PrunedModel(BaseModel):
    @model_serializer(mode="wrap")
    def _drop_none(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
        return {key: value for key, value in handler(self).items() if value is not None}


class ListPage[Item](PrunedModel):
    total: int = Field(
        ...,
        description="Вкупен број на резултати што ги исполнуваат филтрите",
        examples=[178],
    )
    truncated: bool = Field(
        ...,
        description="Дали листата е скратена; ако е, стеснете ги филтрите или користете `offset`",
        examples=[False],
    )
    note: str | None = Field(
        None,
        description="Објаснување кога листата е скратена",
    )
    items: list[Item] = Field(
        default_factory=list,
        description="Резултати",
    )
