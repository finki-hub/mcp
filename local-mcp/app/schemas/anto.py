from pydantic import BaseModel, Field


class AntoQuote(BaseModel):
    quote: str = Field(
        ...,
        description="Случајна Анто цитата: хумористична изрека од ФИНКИ фолклорот за Анто.",
        examples=["Анто не спие, тој хибернира."],
    )
