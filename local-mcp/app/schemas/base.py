from pydantic import BaseModel, SerializerFunctionWrapHandler, model_serializer


class PrunedModel(BaseModel):
    @model_serializer(mode="wrap")
    def _drop_none(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
        return {key: value for key, value in handler(self).items() if value is not None}
