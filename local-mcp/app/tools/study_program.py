from app.schemas.course import AccreditationYear
from app.schemas.study_program import StudyCycle, StudyProgramInfo
from app.utils.http_client import get_degree_programs
from app.utils.query_matcher import transliterate_and_normalize

# Directus names the cycles in English; the tool keeps its Macedonian values.
_CYCLES = {
    "first": StudyCycle.FIRST,
    "second": StudyCycle.SECOND,
    "third": StudyCycle.THIRD,
}


def _name(record: dict, key: str) -> str | None:
    related = record.get(key)
    if isinstance(related, dict):
        return related.get("name") or None
    return None


def _to_program(record: dict, *, details: bool) -> StudyProgramInfo:
    return StudyProgramInfo(
        code=record["code"],
        # The curriculum column's name (КН, СИИС) is the `program` of
        # `list_courses`; only first-cycle programs link one.
        abbreviation=_name(record, "curriculum_program"),
        name=record["name"],
        name_en=record.get("name_en"),
        cycle=_CYCLES[record["cycle"]],
        duration_years=record.get("duration_years"),
        accreditation=record.get("accreditation"),
        language=record.get("language"),
        url=record.get("url"),
        title=record.get("title"),
        title_en=record.get("title_en"),
        ects=record.get("ects"),
        coordinator=_name(record, "coordinator"),
        description=record.get("description") if details else None,
        rules=record.get("rules") if details else None,
    )


def _matches_query(program: StudyProgramInfo, query: str) -> bool:
    fields = (program.code, program.abbreviation, program.name, program.name_en)
    return any(query in transliterate_and_normalize(field) for field in fields if field)


def list_study_programs(
    *,
    cycle: StudyCycle | None = None,
    accreditation: AccreditationYear | None = None,
    query: str | None = None,
    details: bool = False,
) -> list[StudyProgramInfo]:
    normalized_query = transliterate_and_normalize(query) if query else ""
    programs = (
        _to_program(record, details=details) for record in get_degree_programs()
    )
    return [
        program
        for program in programs
        if (cycle is None or program.cycle == cycle)
        and (accreditation is None or program.accreditation == accreditation)
        and (not normalized_query or _matches_query(program, normalized_query))
    ]
