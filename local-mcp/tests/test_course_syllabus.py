import httpx
import pytest
from pydantic import SecretStr

from app.schemas.course import AccreditationYear, SemesterType
from app.tools import course as course_tools
from app.tools.syllabus import get_course_syllabus
from app.utils import pubapi_client
from app.utils.settings import Settings

_COURSES = [
    {
        "name": "Вештачка интелигенција",
        "abbreviation": "ВИ",
        "2018-available": "TRUE",
        "2018-code": "F18L2S030",
        "2018-semester": "4",
        "2023-available": "TRUE",
        "2023-code": "F23L2S030",
        "2023-semester": "4",
    },
    {
        "name": "Менаџмент информациски системи",
        "abbreviation": "МИС",
        "2018-available": "FALSE",
        "2023-available": "TRUE",
        "2023-code": "F23L3W027",
        "2023-semester": "7",
    },
    {"name": "Алгоритми и податочни структури", "abbreviation": "АПС"},
    {
        "name": "Оперативни системи",
        "abbreviation": "ОС",
        "2018-available": "TRUE",
        "2018-code": "F18L2S017",
        "2018-semester": "4",
        "2023-available": "TRUE",
        "2023-semester": "4",
    },
]


def _subject(code: str, **fields: object) -> dict[str, object]:
    return {
        "subjectDto": {
            "code": code,
            "name": "Вештачка интелигенција",
            "abbrevation": None,
            "semesterType": "SUMMER",
            "weeklyLecturesClasses": 3,
            "weeklyAuditoriumClasses": 2,
            "weeklyLabClasses": 0,
        },
        "nameEn": "Artificial Intelligence",
        "defaultSemester": 4,
        "credits": 6.0,
        "language": "Македонски и англиски",
        "learningMethods": "Предавања со презентации, вежби\n    (софтверски\nпакети).",
        "goalsDescription": "Успешниот   студент\nќе знае.",
        "content": (
            "Предавања:\n\t1. За вештачката интелигенција\nЗа агентите\n"
            "    2. Пребарување\n\n\n\nВежби:\n\t1. Python  \n"
        ),
        "goalsDescriptionEn": "The successful student will know.",
        "contentEn": "Lectures:\n1. About AI",
        "bibliography": {
            "books": [
                {
                    "author": "Stuart Russell",
                    "title": "Artificial Intelligence: A Modern Approach",
                    "publisher": "Prentice Hall",
                    "year": 2009,
                },
                {"author": "", "title": "", "publisher": "", "year": 0},
            ],
            "electiveBooks": [],
        },
        "professors": [],
        **fields,
    }


class _Upstream:
    def __init__(self) -> None:
        self.subjects: dict[str, dict[str, object]] = {}
        self.status = 200
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.status != 200:
            return httpx.Response(self.status, text="error")
        code = request.url.path.rsplit("/", 1)[1]
        if code not in self.subjects:
            return httpx.Response(400, text=f"Invalid subject id: {code}")
        return httpx.Response(200, json=self.subjects[code])


@pytest.fixture
def upstream(monkeypatch: pytest.MonkeyPatch) -> _Upstream:
    fake = _Upstream()
    settings = Settings(
        PUBAPI_URL="https://pubapi.test",
        PUBAPI_API_KEY=SecretStr("test-key"),
    )
    monkeypatch.setattr(course_tools, "get_courses", lambda: _COURSES)
    monkeypatch.setattr(pubapi_client, "_settings", settings)
    monkeypatch.setattr(pubapi_client, "_cache", {})
    monkeypatch.setattr(
        pubapi_client,
        "_client",
        lambda api_key: httpx.Client(
            headers={"X-Api-Key": api_key},
            transport=httpx.MockTransport(fake.handler),
        ),
    )
    return fake


@pytest.mark.parametrize(
    "query", ["Вештачка интелигенција", "ВИ", "vestacka inteligencija"]
)
def test_name_and_abbreviation_resolve_to_newest_code(
    upstream: _Upstream, query: str
) -> None:
    upstream.subjects["F23L2S030"] = _subject("F23L2S030")

    result = get_course_syllabus(query)

    assert result.error is None
    assert result.code == "F23L2S030"
    assert result.accreditation == "2023"
    assert result.other_accreditations == ["2018"]
    assert str(upstream.requests[0].url) == "https://pubapi.test/subjects/F23L2S030"
    assert upstream.requests[0].headers["X-Api-Key"] == "test-key"


def test_explicit_accreditation(upstream: _Upstream) -> None:
    upstream.subjects["F18L2S030"] = _subject("F18L2S030")

    result = get_course_syllabus("ВИ", AccreditationYear.Y2018)

    assert result.code == "F18L2S030"
    assert result.accreditation == "2018"
    assert result.other_accreditations == ["2023"]


def test_missing_accreditation_lists_available(upstream: _Upstream) -> None:
    result = get_course_syllabus("МИС", AccreditationYear.Y2018)

    assert result.error is not None
    assert "2018" in result.error
    assert "2023" in result.error
    assert upstream.requests == []


def test_fields_are_normalized(upstream: _Upstream) -> None:
    upstream.subjects["F23L2S030"] = _subject("F23L2S030")

    result = get_course_syllabus("ВИ")

    assert result.content == (
        "Предавања:\n1. За вештачката интелигенција\nЗа агентите\n2. Пребарување\n\n"
        "Вежби:\n1. Python"
    )
    assert result.goals == "Успешниот студент ќе знае."
    assert (
        result.learning_methods
        == "Предавања со презентации, вежби (софтверски пакети)."
    )
    assert result.bibliography == [
        "Stuart Russell, Artificial Intelligence: A Modern Approach, Prentice Hall, 2009"
    ]
    assert result.credits == 6
    assert result.semester == 4
    assert result.semester_type == SemesterType.SUMMER
    assert result.weekly_hours is not None
    assert result.weekly_hours.lectures == 3
    assert result.english_fields is None


def test_english_fallback(upstream: _Upstream) -> None:
    upstream.subjects["F23L2S030"] = _subject(
        "F23L2S030", content="  \n\t", goalsDescription=None
    )

    result = get_course_syllabus("ВИ")

    assert result.content == "Lectures:\n1. About AI"
    assert result.goals == "The successful student will know."
    assert result.english_fields == ["goals", "content"]
    assert result.error is None


def test_empty_content_is_reported(upstream: _Upstream) -> None:
    upstream.subjects["F23L2S030"] = _subject("F23L2S030", content="", contentEn=None)

    result = get_course_syllabus("ВИ")

    assert result.content is None
    assert result.error is not None
    assert "не е внесена" in result.error


def test_course_not_found(upstream: _Upstream) -> None:
    result = get_course_syllabus("Квантна гастрономија")

    assert result.error is not None
    assert result.code is None
    assert upstream.requests == []


def test_course_without_accreditation(upstream: _Upstream) -> None:
    result = get_course_syllabus("АПС")

    assert result.error is not None
    assert "ниедна акредитација" in result.error
    assert upstream.requests == []


def test_available_accreditation_without_code(upstream: _Upstream) -> None:
    result = get_course_syllabus("ОС")

    assert result.accreditation == AccreditationYear.Y2023
    assert result.other_accreditations == [AccreditationYear.Y2018]
    assert result.error is not None
    assert "нема код во акредитација 2023" in result.error
    assert upstream.requests == []

    upstream.subjects["F18L2S017"] = _subject("F18L2S017")
    older = get_course_syllabus("ОС", AccreditationYear.Y2018)

    assert older.code == "F18L2S017"
    assert older.error is None


def test_unknown_code_upstream(upstream: _Upstream) -> None:
    result = get_course_syllabus("ВИ")

    assert result.error == (
        "Силабусот за предметот со код F23L2S030 не е пронајден во pubapi."
    )


@pytest.mark.parametrize("status", [401, 500])
def test_upstream_error(upstream: _Upstream, status: int) -> None:
    upstream.status = status

    result = get_course_syllabus("ВИ")

    assert result.error == str(pubapi_client.SyllabusUnavailableError())
    assert result.code == "F23L2S030"


def test_missing_key_skips_request(
    upstream: _Upstream, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pubapi_client, "_settings", Settings(PUBAPI_API_KEY=""))

    result = get_course_syllabus("ВИ")

    assert result.error == str(pubapi_client.SyllabusUnavailableError())
    assert upstream.requests == []


def test_cache_hit(upstream: _Upstream) -> None:
    upstream.subjects["F23L2S030"] = _subject("F23L2S030")

    first = get_course_syllabus("ВИ")
    second = get_course_syllabus("Вештачка интелигенција")

    assert first.content == second.content
    assert len(upstream.requests) == 1


def test_failures_are_not_cached(upstream: _Upstream) -> None:
    upstream.status = 500
    get_course_syllabus("ВИ")
    upstream.status = 200
    upstream.subjects["F23L2S030"] = _subject("F23L2S030")

    result = get_course_syllabus("ВИ")

    assert result.error is None
    assert len(upstream.requests) == 2
