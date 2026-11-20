from collections import Counter

from app.schemas.stats import StatRow, Stats, StatsMetric
from app.schemas.thesis_search import ThesisKind
from app.tools.directus_lookup import find_staff
from app.tools.schedule import current_timetable
from app.utils.http_client import get_directus_items

# Bounded statistics over Directus, each one aggregate query grouped by
# course, staff member or year: the model gets ranked rows, never the raw
# tables.

DEFAULT_STATS_LIMIT = 10

# The options each metric applies.
# Directus aggregate query parameters.
_SUM = "aggregate[sum]"
_COUNT = "aggregate[count]"
_GROUP_BY = "groupBy[]"

_OPTIONS: dict[StatsMetric, set[str]] = {
    StatsMetric.TOP_COURSES: {"academic_year"},
    StatsMetric.THESES_PER_YEAR: {"kind", "staff"},
    StatsMetric.TOP_MENTORS: {"year", "kind"},
    StatsMetric.TEACHING_LOAD: set(),
}

_THESIS_TABLES = {
    ThesisKind.BACHELOR: ("bachelor_theses", "bachelor_thesis_staff"),
    ThesisKind.MASTER: ("master_theses", "master_thesis_staff"),
}


def _number(value: object) -> int:
    # Directus returns aggregates as strings (or null for an empty group).
    try:
        return round(float(str(value)))
    except TypeError, ValueError:
        return 0


def _names(collection: str) -> dict[int, str]:
    rows = get_directus_items(collection, {"fields": "id,name", "limit": -1})
    return {row["id"]: row["name"] for row in rows}


def _ranked(rows: list[StatRow], limit: int) -> tuple[int, list[StatRow]]:
    ordered = sorted(rows, key=lambda row: (-row.value, row.label))
    return len(ordered), ordered[:limit]


def _enrolled_years() -> list[str]:
    # The newest academic year with any enrollment counted: the current one
    # has none until its Moodle snapshot is imported.
    rows = get_directus_items(
        "course_enrollments",
        {_SUM: "count", _GROUP_BY: "academic_year", "limit": -1},
    )
    labels = {
        row["id"]: row["label"]
        for row in get_directus_items(
            "academic_years",
            {"fields": "id,label", "limit": -1},
        )
    }
    return sorted(
        (
            labels[row["academic_year"]]
            for row in rows
            if row.get("academic_year") in labels
            and _number((row.get("sum") or {}).get("count")) > 0
        ),
        reverse=True,
    )


def _top_courses(academic_year: str | None, limit: int) -> Stats:
    years = _enrolled_years()
    if not years:
        return Stats(metric=StatsMetric.TOP_COURSES, error="Нема податоци за запишани.")
    if academic_year is not None and academic_year not in years:
        return Stats(
            metric=StatsMetric.TOP_COURSES,
            error=f"Нема запишани за академската година {academic_year}.",
            suggestions=years[:5],
        )
    year = academic_year or years[0]
    rows = get_directus_items(
        "course_enrollments",
        {
            _SUM: "count",
            _GROUP_BY: "course",
            "filter[academic_year][label][_eq]": year,
            "limit": -1,
        },
    )
    names = _names("courses")
    counted = [
        StatRow(label=names[row["course"]], value=value)
        for row in rows
        if row.get("course") in names
        and (value := _number((row.get("sum") or {}).get("count"))) > 0
    ]
    total, top = _ranked(counted, limit)
    return Stats(
        metric=StatsMetric.TOP_COURSES,
        scope=year,
        unit="запишани студенти",
        total=total,
        rows=top or None,
    )


def _theses_per_year(kind: ThesisKind | None, staff_id: int | None) -> Stats:
    per_year: dict[int, Counter[str]] = {}
    for each in [kind] if kind else list(ThesisKind):
        theses, staff_table = _THESIS_TABLES[each]
        if staff_id is None:
            rows = get_directus_items(
                theses,
                {_COUNT: "id", _GROUP_BY: "year", "limit": -1},
            )
        else:
            rows = get_directus_items(
                staff_table,
                {
                    _COUNT: "id",
                    _GROUP_BY: "year",
                    "filter[staff][_eq]": staff_id,
                    "filter[role][_eq]": "mentor",
                    "limit": -1,
                },
            )
        for row in rows:
            if row.get("year") is not None:
                count = _number((row.get("count") or {}).get("id"))
                per_year.setdefault(row["year"], Counter())[each.value] += count
    rows_out = [
        StatRow(label=str(year), value=sum(parts.values()), parts=dict(parts))
        for year, parts in sorted(per_year.items(), reverse=True)
    ]
    return Stats(
        metric=StatsMetric.THESES_PER_YEAR,
        unit="трудови" if staff_id is None else "трудови како ментор",
        total=len(rows_out),
        rows=rows_out or None,
    )


def _top_mentors(kind: ThesisKind | None, year: int | None, limit: int) -> Stats:
    per_staff: dict[int, Counter[str]] = {}
    for each in [kind] if kind else list(ThesisKind):
        _theses, staff_table = _THESIS_TABLES[each]
        params: dict[str, str | int] = {
            _COUNT: "id",
            _GROUP_BY: "staff",
            "filter[role][_eq]": "mentor",
            "limit": -1,
        }
        if year is not None:
            params["filter[year][_eq]"] = year
        for row in get_directus_items(staff_table, params):
            if row.get("staff") is not None:
                count = _number((row.get("count") or {}).get("id"))
                per_staff.setdefault(row["staff"], Counter())[each.value] += count
    names = _names("staff")
    total, top = _ranked(
        [
            StatRow(label=names[staff], value=sum(parts.values()), parts=dict(parts))
            for staff, parts in per_staff.items()
            if staff in names
        ],
        limit,
    )
    return Stats(
        metric=StatsMetric.TOP_MENTORS,
        scope=str(year) if year is not None else "сите години",
        unit="трудови како ментор",
        total=total,
        rows=top or None,
    )


def _teaching_load(limit: int) -> Stats:
    timetable = current_timetable()
    if timetable is None:
        return Stats(metric=StatsMetric.TEACHING_LOAD, error="Нема главен распоред.")
    rows = get_directus_items(
        "course_teaching",
        {
            _SUM: "periods",
            "aggregate[countDistinct]": "course",
            _GROUP_BY: "staff",
            "filter[timetable][_eq]": timetable["id"],
            "limit": -1,
        },
    )
    names = _names("staff")
    total, top = _ranked(
        [
            StatRow(
                label=names[row["staff"]],
                value=_number((row.get("sum") or {}).get("periods")),
                parts={
                    "courses": _number((row.get("countDistinct") or {}).get("course"))
                },
            )
            for row in rows
            if row.get("staff") in names
        ],
        limit,
    )
    return Stats(
        metric=StatsMetric.TEACHING_LOAD,
        scope=timetable["title"],
        unit="неделни часови",
        total=total,
        rows=top or None,
    )


def stats(
    metric: StatsMetric,
    *,
    academic_year: str | None = None,
    year: int | None = None,
    kind: ThesisKind | None = None,
    staff: str | None = None,
    limit: int = DEFAULT_STATS_LIMIT,
) -> Stats:
    given = {
        name
        for name, value in (
            ("academic_year", academic_year),
            ("year", year),
            ("kind", kind),
            ("staff", staff.strip() if staff else None),
        )
        if value
    }
    if unused := sorted(given - _OPTIONS[metric]):
        # A filter the metric cannot apply would look applied in the answer.
        return Stats(
            metric=metric,
            error=f"{metric.value} не прима: {', '.join(unused)}.",
        )
    if metric == StatsMetric.TOP_COURSES:
        return _top_courses(academic_year, limit)
    if metric == StatsMetric.TOP_MENTORS:
        return _top_mentors(kind, year, limit)
    if metric == StatsMetric.TEACHING_LOAD:
        return _teaching_load(limit)

    staff_id: int | None = None
    scope: str | None = None
    if staff and staff.strip():
        found = find_staff(staff)
        if found.record is None:
            return Stats(
                metric=metric, error=found.error, suggestions=found.suggestions
            )
        staff_id, scope = found.record["id"], found.record["name"]
    result = _theses_per_year(kind, staff_id)
    result.scope = scope
    return result
