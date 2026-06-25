from pydantic import BaseModel, Field


class StaffData(BaseModel):
    course: str = Field(
        ...,
        description="Името на предметот",
        examples=["Структурно програмирање"],
    )
    professors: list[str] = Field(
        ...,
        description="Листа на професори кои го предаваат предметот",
        examples=[["Ѓорѓи Маџаров", "Ана Мадевска Богданова"]],
    )
    assistants: list[str] = Field(
        ...,
        description="Листа на асистенти на предметот",
        examples=[["Александар Тенев", "Влатко Спасев"]],
    )
    error: str | None = Field(
        None,
        description="Порака за грешка доколку предметот не е пронајден или има друг проблем",
        examples=["Course 'структурно програмирање' not found"],
    )
    suggestions: list[str] | None = Field(
        None,
        description="Листа на предложени имиња на предмети доколку нема точно совпаѓање",
        examples=[["Алгоритми и податочни структури", "Бази на податоци"]],
    )
    match_info: dict | None = Field(
        None,
        description="Метаподатоци за процесот на совпаѓање: оригиналното барање, пронајдениот предмет, оценката на сличност и типот на совпаѓање",
        examples=[
            {
                "original_query": "веб програмирање",
                "matched_course": "Веб програмирање",
                "similarity_score": 95,
                "match_type": "fuzzy",
            },
        ],
    )
