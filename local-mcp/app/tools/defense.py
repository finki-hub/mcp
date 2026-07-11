import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Final, Protocol, assert_never

from app.schemas.defense import DefenseMatch, parse_upstream_student
from app.utils.query_matcher import resolve_query, transliterate_and_normalize

MAX_DEFENSE_MATCHES: Final = 20
MIN_DEFENSE_NAME_LENGTH: Final = 3
_INDEX_PATTERN: Final = re.compile(r"[0-9]+")
_DATE_FORMAT: Final = "%d.%m.%Y"


class DefenseRecord(Protocol):
    @property
    def student(self) -> str: ...

    @property
    def mentor(self) -> str: ...

    @property
    def title(self) -> str: ...


@dataclass(frozen=True, slots=True)
class StudentIndexFilter:
    canonical_index: str


@dataclass(frozen=True, slots=True)
class StudentNameFilter:
    name: str


type StudentFilter = StudentIndexFilter | StudentNameFilter


class DefenseLookupCategory(StrEnum):
    EMPTY = "Внесете име или индекс на студентот."
    SHORT = "Барањето е прекратко; внесете барем 3 знаци."
    NOT_FOUND = "Не е пронајден студент за внесеното барање."
    AMBIGUOUS = "Повеќе студенти одговараат на внесеното барање."


@dataclass(frozen=True, slots=True)
class DefenseLookupSuccess[RecordT: DefenseRecord]:
    record: RecordT
    canonical_index: str
    normalized_name: str


@dataclass(frozen=True, slots=True)
class DefenseLookupFailure:
    category: DefenseLookupCategory
    suggestions: tuple[DefenseMatch, ...] = ()


type DefenseLookupOutcome[RecordT: DefenseRecord] = (
    DefenseLookupSuccess[RecordT] | DefenseLookupFailure
)


def strip_list_filter(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def parse_student_filter(value: str) -> StudentFilter:
    stripped = value.strip()
    if _INDEX_PATTERN.fullmatch(stripped) is not None:
        return StudentIndexFilter(stripped.lstrip("0") or "0")
    return StudentNameFilter(stripped)


def parse_optional_student_filter(value: str | None) -> StudentFilter | None:
    stripped = strip_list_filter(value)
    if stripped is None:
        return None
    return parse_student_filter(stripped)


def collapse_defense_records[RecordT: DefenseRecord](
    records: Sequence[RecordT],
    date_getter: Callable[[RecordT], str],
) -> list[RecordT]:
    groups: dict[str, list[RecordT]] = {}
    for record in records:
        index = parse_upstream_student(record.student).canonical_index
        groups.setdefault(index, []).append(record)

    selected: list[RecordT] = []
    for group in groups.values():
        chosen = group[0]
        chosen_date = None
        for record in group:
            parsed_date = _parse_date(date_getter(record))
            if parsed_date is not None and (
                chosen_date is None or parsed_date > chosen_date
            ):
                chosen = record
                chosen_date = parsed_date
        selected.append(chosen)
    return selected


def filter_defense_records[RecordT: DefenseRecord](
    records: Sequence[RecordT],
    *,
    student: StudentFilter | None = None,
    mentor: str | None = None,
    title: str | None = None,
) -> list[RecordT]:
    candidates = list(records)
    if student is not None:
        candidates = _filter_student(candidates, student)
    mentor_query = strip_list_filter(mentor)
    if mentor_query is not None:
        candidates = _filter_grouped(candidates, mentor_query, lambda row: row.mentor)
    title_query = strip_list_filter(title)
    if title_query is not None:
        candidates = _filter_titles(candidates, title_query)
    return candidates


def to_defense_matches(records: Sequence[DefenseRecord]) -> list[DefenseMatch]:
    return [
        DefenseMatch(
            student=row.student,
            mentor=row.mentor,
            title=row.title,
        )
        for row in records[:MAX_DEFENSE_MATCHES]
    ]


def resolve_defense_lookup[RecordT: DefenseRecord](
    records: Sequence[RecordT],
    student: StudentFilter,
) -> DefenseLookupOutcome[RecordT]:
    match student:
        case StudentIndexFilter(canonical_index=index):
            matches = [
                row
                for row in records
                if parse_upstream_student(row.student).canonical_index == index
            ]
            if not matches:
                return DefenseLookupFailure(DefenseLookupCategory.NOT_FOUND)
            parsed = parse_upstream_student(matches[0].student)
            return DefenseLookupSuccess(
                record=matches[0],
                canonical_index=index,
                normalized_name=transliterate_and_normalize(parsed.name),
            )
        case StudentNameFilter(name=name):
            return _resolve_name_lookup(records, name)
        case unreachable:
            assert_never(unreachable)


def _parse_date(value: str) -> date | None:
    try:
        parsed = time.strptime(value.strip(), _DATE_FORMAT)
    except ValueError:
        return None
    return date(parsed.tm_year, parsed.tm_mon, parsed.tm_mday)


def _representatives[RecordT: DefenseRecord](
    records: Sequence[RecordT],
    getter: Callable[[RecordT], str],
) -> list[str]:
    representatives: dict[str, str] = {}
    for record in records:
        value = getter(record)
        representatives.setdefault(transliterate_and_normalize(value), value)
    return list(representatives.values())


def _resolved_normalizations[RecordT: DefenseRecord](
    records: Sequence[RecordT],
    query: str,
    getter: Callable[[RecordT], str],
) -> set[str]:
    resolution = resolve_query(query, _representatives(records, getter))
    match = resolution["match"]
    if match is not None:
        return {transliterate_and_normalize(match)}
    if resolution["match_type"] == "ambiguous":
        return {
            transliterate_and_normalize(candidate)
            for candidate in resolution["candidates"]
        }
    return set()


def _filter_grouped[RecordT: DefenseRecord](
    records: Sequence[RecordT],
    query: str,
    getter: Callable[[RecordT], str],
) -> list[RecordT]:
    selected = _resolved_normalizations(records, query, getter)
    return [
        record
        for record in records
        if transliterate_and_normalize(getter(record)) in selected
    ]


def _student_name(record: DefenseRecord) -> str:
    return parse_upstream_student(record.student).name


def _filter_student[RecordT: DefenseRecord](
    records: Sequence[RecordT],
    student: StudentFilter,
) -> list[RecordT]:
    match student:
        case StudentIndexFilter(canonical_index=index):
            return [
                row
                for row in records
                if parse_upstream_student(row.student).canonical_index == index
            ]
        case StudentNameFilter(name=name):
            return _filter_grouped(records, name, _student_name)
        case unreachable:
            assert_never(unreachable)


def _filter_titles[RecordT: DefenseRecord](
    records: Sequence[RecordT],
    query: str,
) -> list[RecordT]:
    normalized_query = transliterate_and_normalize(query)
    substring_groups = {
        transliterate_and_normalize(representative)
        for representative in _representatives(records, lambda row: row.title)
        if normalized_query in transliterate_and_normalize(representative)
    }
    if substring_groups:
        return [
            row
            for row in records
            if transliterate_and_normalize(row.title) in substring_groups
        ]
    return _filter_grouped(records, query, lambda row: row.title)


def _resolve_name_lookup[RecordT: DefenseRecord](
    records: Sequence[RecordT],
    name: str,
) -> DefenseLookupOutcome[RecordT]:
    if not name:
        return DefenseLookupFailure(DefenseLookupCategory.EMPTY)
    if len(name) < MIN_DEFENSE_NAME_LENGTH:
        return DefenseLookupFailure(DefenseLookupCategory.SHORT)

    resolution = resolve_query(name, _representatives(records, _student_name))
    matched = resolution["match"]
    if matched is None:
        category = (
            DefenseLookupCategory.AMBIGUOUS
            if resolution["match_type"] == "ambiguous"
            else DefenseLookupCategory.NOT_FOUND
        )
        suggested_norms = {
            transliterate_and_normalize(candidate)
            for candidate in resolution["candidates"]
        }
        suggestions = [
            row
            for row in records
            if transliterate_and_normalize(_student_name(row)) in suggested_norms
        ]
        return DefenseLookupFailure(category, tuple(to_defense_matches(suggestions)))

    normalized_name = transliterate_and_normalize(matched)
    matches = [
        row
        for row in records
        if transliterate_and_normalize(_student_name(row)) == normalized_name
    ]
    indexes = {parse_upstream_student(row.student).canonical_index for row in matches}
    if len(indexes) != 1:
        return DefenseLookupFailure(
            DefenseLookupCategory.AMBIGUOUS,
            tuple(to_defense_matches(matches)),
        )
    canonical_index = next(iter(indexes))
    return DefenseLookupSuccess(matches[0], canonical_index, normalized_name)
