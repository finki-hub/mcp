from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated

import anyio
from mcp.server import MCPServer
from mcp.types import CallToolResult, ToolAnnotations
from pydantic import Field
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from app.schemas.announcement import (
    AnnouncementDetail,
    AnnouncementSearchResult,
    Board,
)
from app.schemas.anto import AntoQuote
from app.schemas.base import ListPage
from app.schemas.course import (
    AccreditationYear,
    CourseList,
    CourseStatus,
    CourseTag,
    SemesterType,
    StudyProgram,
)
from app.schemas.course_details import CourseDetails, CourseInclude
from app.schemas.defense import DiplomaResult, MasterResult
from app.schemas.leadership import Leadership, LeadershipBody
from app.schemas.room import RoomData, RoomLocation, RoomMatch, RoomType
from app.schemas.schedule import Schedule
from app.schemas.session import ExamSessionScheduleFile
from app.schemas.staff import (
    StaffMatch,
    StaffPosition,
    StaffTitle,
)
from app.schemas.staff_details import StaffDetails, StaffInclude
from app.schemas.stats import Stats, StatsMetric
from app.schemas.study_program import StudyCycle, StudyProgramInfo
from app.schemas.thesis_search import ThesisKind, ThesisRole, ThesisSearch
from app.schemas.timetable import (
    TimetableDay,
    TimetableEntity,
    TimetableEntry,
    TimetableLessonType,
    TimetableSummary,
)
from app.tools.announcement import get_announcement, search_announcements
from app.tools.anto import get_random_anto_quote
from app.tools.course import (
    DEFAULT_COURSE_LIMIT,
    list_courses,
)
from app.tools.course_details import get_course
from app.tools.diploma import get_diploma
from app.tools.leadership import get_leadership
from app.tools.master import get_master
from app.tools.room import DEFAULT_ROOM_LIMIT, get_room_data, list_rooms
from app.tools.schedule import schedule
from app.tools.session import DEFAULT_SESSION_LIMIT, list_exam_session_schedules
from app.tools.staff import list_staff
from app.tools.staff_details import get_staff
from app.tools.stats import DEFAULT_STATS_LIMIT, stats
from app.tools.study_program import list_study_programs
from app.tools.thesis_search import DEFAULT_THESIS_LIMIT, find_theses
from app.tools.timetable import (
    DEFAULT_ENTITY_LIMIT,
    DEFAULT_TIMETABLE_LIMIT,
    list_timetable_courses,
    list_timetable_entries,
    list_timetable_groups,
    list_timetable_professors,
    list_timetable_rooms,
    list_timetables,
)
from app.utils.analytics import (
    capture_lifecycle_event,
    init_analytics,
    shutdown_analytics,
    track_tool,
)
from app.utils.settings import Settings
from app.utils.tool_result import compact_result

settings = Settings()

type _Offset = Annotated[
    int,
    Field(
        description="Број на резултати што се прескокнуваат (за следна страница).",
        ge=0,
    ),
]


def make_app(settings: Settings) -> MCPServer:
    @asynccontextmanager
    async def lifespan(_server: MCPServer) -> AsyncIterator[None]:
        init_analytics(settings)
        tools = await _server.list_tools()
        capture_lifecycle_event("server_started", properties={"tool_count": len(tools)})
        try:
            yield
        finally:
            capture_lifecycle_event("server_stopped")
            shutdown_analytics()

    mcp = MCPServer(
        "FastMCP",
        lifespan=lifespan,
    )

    @mcp.custom_route("/health", methods=["GET", "HEAD"])
    async def health_check(request: Request) -> PlainTextResponse:
        return PlainTextResponse("OK")

    @mcp.tool(
        name="list_exam_session_schedules",
        description=(
            "Враќа датотеки со распореди за испитни сесии и колоквиумски недели, "
            "најновите прво. Секоја ставка содржи ознака на сесијата и линк за "
            "преземање. Филтрирај по академска година или клучен збор (на пр. „Јуни“, "
            "„Колоквиум“) наместо да ги листаш сите."
        ),
        annotations=ToolAnnotations(
            title="Датотеки со распореди за испитни сесии",
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
            readOnlyHint=True,
        ),
    )
    @track_tool("list_exam_session_schedules")
    async def list_exam_session_schedules_tool(
        *,
        academic_year: Annotated[
            str | None,
            Field(
                description="Академска година во формат ГГГГ/ГГГГ.",
                examples=["2025/2026"],
                pattern=r"^\d{4}/\d{4}$",
            ),
        ] = None,
        query: Annotated[
            str | None,
            Field(
                description=(
                    "Дел од ознаката на сесијата (кирилица или латиница), на пр. "
                    "„Јуни“, „Септември“, „Колоквиум“, „Зимски“."
                ),
                examples=["Јуни", "kolokvium"],
                max_length=128,
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(description="Максимален број на резултати.", ge=1, le=100),
        ] = DEFAULT_SESSION_LIMIT,
        offset: _Offset = 0,
    ) -> Annotated[CallToolResult, ListPage[ExamSessionScheduleFile]]:
        return compact_result(
            list_exam_session_schedules(
                academic_year=academic_year,
                query=query,
                limit=limit,
                offset=offset,
            )
        )

    @mcp.tool(
        name="get_random_anto_quote",
        description="Враќа случајна Анто цитата: хумористична изрека од ФИНКИ фолклорот за Анто.",
        annotations=ToolAnnotations(
            title="Случајна Анто цитата",
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=True,
            readOnlyHint=True,
        ),
    )
    @track_tool("get_random_anto_quote")
    async def get_random_anto_quote_tool() -> AntoQuote:
        return get_random_anto_quote()

    @mcp.tool(
        name="list_timetables",
        description=(
            "Враќа листа на распореди, најновите прво. Секоја ставка содржи ID, "
            "наслов, почетен датум, академска година и дали е активен. Обично не е "
            "потребна: другите алатки за распоред стандардно го користат моментално "
            "активниот распоред."
        ),
        annotations=ToolAnnotations(
            title="Листа на распореди",
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
            readOnlyHint=True,
        ),
    )
    @track_tool("list_timetables")
    async def list_timetables_tool(
        *,
        academic_year: Annotated[
            int | None,
            Field(
                description="Почетна година на академската година (2025 = 2025/2026).",
                examples=[2025],
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(description="Максимален број на резултати.", ge=1, le=100),
        ] = DEFAULT_TIMETABLE_LIMIT,
        offset: _Offset = 0,
    ) -> Annotated[CallToolResult, ListPage[TimetableSummary]]:
        return compact_result(
            list_timetables(academic_year=academic_year, limit=limit, offset=offset)
        )

    @mcp.tool(
        name="list_timetable_groups",
        description=(
            "Враќа групи во распоред (година на студии и студиска програма, на пр. "
            "„2г-КН“, „1y-SEIS“). Секоја ставка содржи ID и име; ID може да се "
            "користи како `group_id` во `list_timetable_entries`. Користи `query` за "
            "една програма или година."
        ),
        annotations=ToolAnnotations(
            title="Групи во распоред",
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
            readOnlyHint=True,
        ),
    )
    @track_tool("list_timetable_groups")
    async def list_timetable_groups_tool(
        id: Annotated[
            str | None,
            Field(
                description=(
                    "ID на распоредот добиен од `list_timetables`. Ако не е зададено, "
                    "се користи моментално активниот распоред."
                ),
                examples=["28"],
            ),
        ] = None,
        query: Annotated[
            str | None,
            Field(
                description="Дел од името на групата (кирилица или латиница).",
                examples=["КН", "3г", "SEIS"],
                max_length=128,
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(description="Максимален број на резултати.", ge=1, le=500),
        ] = DEFAULT_ENTITY_LIMIT,
        offset: _Offset = 0,
    ) -> Annotated[CallToolResult, ListPage[TimetableEntity]]:
        return compact_result(
            list_timetable_groups(id, query=query, limit=limit, offset=offset)
        )

    @mcp.tool(
        name="list_timetable_professors",
        description=(
            "Враќа професори во распоред. Секоја ставка содржи ID и име; ID може да се "
            "користи како `professor_id` во `list_timetable_entries`."
        ),
        annotations=ToolAnnotations(
            title="Професори во распоред",
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
            readOnlyHint=True,
        ),
    )
    @track_tool("list_timetable_professors")
    async def list_timetable_professors_tool(
        id: Annotated[
            str | None,
            Field(
                description=(
                    "ID на распоредот добиен од `list_timetables`. Ако не е зададено, "
                    "се користи моментално активниот распоред."
                ),
                examples=["28"],
            ),
        ] = None,
    ) -> list[TimetableEntity]:
        return list_timetable_professors(id)

    @mcp.tool(
        name="list_timetable_rooms",
        description=(
            "Враќа простории во распоред. Секоја ставка содржи ID и име; ID може да се "
            "користи како `room_id` во `list_timetable_entries`."
        ),
        annotations=ToolAnnotations(
            title="Простории во распоред",
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
            readOnlyHint=True,
        ),
    )
    @track_tool("list_timetable_rooms")
    async def list_timetable_rooms_tool(
        id: Annotated[
            str | None,
            Field(
                description=(
                    "ID на распоредот добиен од `list_timetables`. Ако не е зададено, "
                    "се користи моментално активниот распоред."
                ),
                examples=["28"],
            ),
        ] = None,
    ) -> list[TimetableEntity]:
        return list_timetable_rooms(id)

    @mcp.tool(
        name="list_timetable_courses",
        description=(
            "Враќа предмети во распоред, секој предмет еднаш. Секоја ставка содржи ID "
            "и име; ID може да се користи како `course_id` во `list_timetable_entries` "
            "(ги враќа и предавањата и вежбите). Користи `query` за да најдеш "
            "конкретен предмет."
        ),
        annotations=ToolAnnotations(
            title="Предмети во распоред",
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
            readOnlyHint=True,
        ),
    )
    @track_tool("list_timetable_courses")
    async def list_timetable_courses_tool(
        id: Annotated[
            str | None,
            Field(
                description=(
                    "ID на распоредот добиен од `list_timetables`. Ако не е зададено, "
                    "се користи моментално активниот распоред."
                ),
                examples=["28"],
            ),
        ] = None,
        query: Annotated[
            str | None,
            Field(
                description="Дел од името на предметот (кирилица или латиница).",
                examples=["Бази на податоци", "veb"],
                max_length=256,
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(description="Максимален број на резултати.", ge=1, le=500),
        ] = DEFAULT_ENTITY_LIMIT,
        offset: _Offset = 0,
    ) -> Annotated[CallToolResult, ListPage[TimetableEntity]]:
        return compact_result(
            list_timetable_courses(id, query=query, limit=limit, offset=offset)
        )

    @mcp.tool(
        name="list_timetable_entries",
        description=(
            "Враќа термини од распоред што ги задоволуваат зададените ID филтри "
            "(комбинирани со И). Мора да биде зададен барем еден од `group_id`, "
            "`professor_id`, `room_id` или `course_id`; инаку враќа празна листа. "
            "За тековниот распоред по име користи `schedule`; оваа е за постари "
            "и прво-неделни распореди."
        ),
        annotations=ToolAnnotations(
            title="Термини од распоред по ID филтри",
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
            readOnlyHint=True,
        ),
    )
    @track_tool("list_timetable_entries")
    async def list_timetable_entries_tool(
        *,
        id: Annotated[
            str | None,
            Field(
                description=(
                    "ID на распоредот добиен од `list_timetables`. Ако не е зададено, "
                    "се користи моментално активниот распоред."
                ),
                examples=["28"],
            ),
        ] = None,
        group_id: Annotated[
            str | None,
            Field(
                description="ID на групата добиен од `list_timetable_groups`.",
                examples=["15"],
            ),
        ] = None,
        professor_id: Annotated[
            str | None,
            Field(
                description="ID на професорот добиен од `list_timetable_professors`.",
                examples=["-123"],
            ),
        ] = None,
        room_id: Annotated[
            str | None,
            Field(
                description="ID на просторијата добиен од `list_timetable_rooms`.",
                examples=["9"],
            ),
        ] = None,
        course_id: Annotated[
            str | None,
            Field(
                description=(
                    "ID на предметот добиен од `list_timetable_courses`; ги вклучува "
                    "сите типови на термини за предметот."
                ),
                examples=["30"],
            ),
        ] = None,
        day: Annotated[
            TimetableDay | None,
            Field(
                description="Ден во неделата.",
                examples=["Понеделник"],
            ),
        ] = None,
        lesson_type: Annotated[
            TimetableLessonType | None,
            Field(
                description="Тип на термин: предавање, аудиториски вежби или лабораториски вежби.",
                examples=["предавање"],
            ),
        ] = None,
        start_after: Annotated[
            str | None,
            Field(
                description="Вклучува само термини што почнуваат во или по ова време (HH:MM).",
                examples=["10:00"],
                pattern=r"^\d{2}:\d{2}$",
            ),
        ] = None,
        end_before: Annotated[
            str | None,
            Field(
                description="Вклучува само термини што завршуваат во или пред ова време (HH:MM).",
                examples=["14:00"],
                pattern=r"^\d{2}:\d{2}$",
            ),
        ] = None,
    ) -> list[TimetableEntry]:
        return list_timetable_entries(
            id=id,
            group_id=group_id,
            professor_id=professor_id,
            room_id=room_id,
            course_id=course_id,
            day=day,
            lesson_type=lesson_type,
            start_after=start_after,
            end_before=end_before,
        )

    @mcp.tool(
        name="list_courses",
        description=(
            "Враќа листа на предмети (име и кратенка) што ги задоволуваат зададените "
            "филтри (комбинирани со И). Сите филтри се опционални; користи ги за да "
            "добиеш кратка листа наместо сите предмети. Програма, статус, семестар и "
            "тип на семестар се проверуваат заедно во рамки на една акредитација; "
            "предметот се вклучува ако барем една акредитација ги исполнува, а "
            "совпаднатите акредитации се прикажуваат со семестар. Филтрите за број на "
            "запишани студенти (`min_participants`, `max_participants`, "
            "`sort_by_participants`) додаваат број на запишани по предмет, така што "
            "не е потребно `get_course` за секој предмет. Резултатот е "
            "ограничен со `limit`; ако `truncated` е true, стесни ги филтрите или "
            "користи `offset`. Детали за предмет: `get_course`."
        ),
        annotations=ToolAnnotations(
            title="Листа на предмети по филтри",
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
            readOnlyHint=True,
        ),
    )
    @track_tool("list_courses")
    async def list_courses_tool(
        *,
        program: Annotated[
            StudyProgram | None,
            Field(
                description=(
                    "Студиска програма (прв циклус); само предмети што се нудат во "
                    "неа. Кодовите и имињата се во `list_study_programs`."
                ),
                examples=["КН"],
            ),
        ] = None,
        status: Annotated[
            CourseStatus | None,
            Field(
                description=(
                    "Статус на предметот: „задолжителен“ или „изборен“. Ако е зададена "
                    "и студиска програма, важи само за таа програма; инаку важи за која било "
                    "програма."
                ),
            ),
        ] = None,
        semester: Annotated[
            int | None,
            Field(description="Семестар (1–8).", ge=1, le=8),
        ] = None,
        semester_type: Annotated[
            SemesterType | None,
            Field(
                description=(
                    "Тип на семестар: „зимски“ (непарни семестри 1, 3, 5, 7) или "
                    "„летен“ (парни семестри 2, 4, 6, 8)."
                ),
                examples=["зимски"],
            ),
        ] = None,
        accreditation: Annotated[
            AccreditationYear | None,
            Field(
                description="Ограничи на конкретна акредитација.",
                examples=["2018", "2023"],
            ),
        ] = None,
        tags: Annotated[
            list[CourseTag] | None,
            Field(
                description="Тематски ознаки (тагови); предметот мора да ги содржи сите наведени.",
                examples=[["AI"]],
            ),
        ] = None,
        professors: Annotated[
            list[str] | None,
            Field(
                description="Имиња на професори; предметот мора да ги содржи сите наведени (толерантно/fuzzy совпаѓање).",
                examples=[["Димитар Трајанов"]],
            ),
        ] = None,
        assistants: Annotated[
            list[str] | None,
            Field(
                description="Имиња на асистенти; предметот мора да ги содржи сите наведени (толерантно/fuzzy совпаѓање).",
                examples=[["Ана Тодоровска"]],
            ),
        ] = None,
        query: Annotated[
            str | None,
            Field(
                description=(
                    "Дел од името или кратенка на предметот (кирилица или латиница)."
                ),
                examples=["програмирање", "АПС", "bazi"],
                max_length=256,
            ),
        ] = None,
        participants_year: Annotated[
            str | None,
            Field(
                description=(
                    "Академска година (ГГГГ/ГГГГ) за бројот на запишани студенти. "
                    "Стандардно последната година со податоци; за тековната година "
                    "предметите од семестар што уште не почнал имаат 0 запишани."
                ),
                examples=["2025/2026"],
                pattern=r"^\d{4}/\d{4}$",
            ),
        ] = None,
        min_participants: Annotated[
            int | None,
            Field(
                description=(
                    "Минимален број на запишани студенти (вклучително). Предметите "
                    "со 0 запишани (не се изведуваат или немаат податоци за таа "
                    "година) се изоставуваат освен ако е зададено 0."
                ),
                ge=0,
                examples=[5],
            ),
        ] = None,
        max_participants: Annotated[
            int | None,
            Field(
                description=(
                    "Максимален број на запишани студенти (вклучително). Предметите "
                    "со 0 запишани се изоставуваат освен ако `min_participants` е 0."
                ),
                ge=0,
                examples=[15],
            ),
        ] = None,
        sort_by_participants: Annotated[
            bool,
            Field(
                description=(
                    "Подреди по број на запишани студенти, најмногу прво; предметите "
                    "со 0 запишани се на крајот."
                ),
            ),
        ] = False,
        limit: Annotated[
            int,
            Field(description="Максимален број на предмети.", ge=1, le=200),
        ] = DEFAULT_COURSE_LIMIT,
        offset: _Offset = 0,
    ) -> Annotated[CallToolResult, CourseList]:
        return compact_result(
            list_courses(
                program=program,
                status=status,
                semester=semester,
                semester_type=semester_type,
                accreditation=accreditation,
                tags=tags,
                professors=professors,
                assistants=assistants,
                query=query,
                participants_year=participants_year,
                min_participants=min_participants,
                max_participants=max_participants,
                sort_by_participants=sort_by_participants,
                limit=limit,
                offset=offset,
            )
        )

    @mcp.tool(
        name="list_study_programs",
        description=(
            "Враќа студиски програми на ФИНКИ (прв, втор и трет циклус): код, име на "
            "македонски и англиски, циклус, времетраење во години, акредитација, "
            "јазик на настава (само кога е официјално потврден), стекнато звање, "
            "вкупно ЕКТС, координатор (магистерски) и линк. Со `details` враќа и "
            "опис и правила на наставната програма (изборни предмети по тежина). "
            "Кратенката (на пр. „КН“) се користи како `program` во `list_courses`."
        ),
        annotations=ToolAnnotations(
            title="Студиски програми",
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
            readOnlyHint=True,
        ),
    )
    @track_tool("list_study_programs")
    async def list_study_programs_tool(
        *,
        cycle: Annotated[
            StudyCycle | None,
            Field(
                description=(
                    "Циклус: „прв“ (додипломски), „втор“ (магистерски) или „трет“ "
                    "(докторски)."
                ),
                examples=["прв"],
            ),
        ] = None,
        accreditation: Annotated[
            AccreditationYear | None,
            Field(
                description="Година на акредитација.",
                examples=["2023"],
            ),
        ] = None,
        query: Annotated[
            str | None,
            Field(
                description=(
                    "Дел од името, кодот или кратенката на програмата (кирилица или "
                    "латиница)."
                ),
                examples=["КН", "seis", "софтверско"],
                max_length=256,
            ),
        ] = None,
        details: Annotated[
            bool,
            Field(
                description=(
                    "Дали да се вклучат описот и правилата на наставната програма; "
                    "се вклучуваат само кога филтрите даваат најмногу 5 програми, "
                    "па користи го со `query`."
                ),
            ),
        ] = False,
    ) -> Annotated[CallToolResult, list[StudyProgramInfo]]:
        programs = await anyio.to_thread.run_sync(
            lambda: list_study_programs(
                cycle=cycle,
                accreditation=accreditation,
                query=query,
                details=details,
            ),
        )
        return compact_result(programs)

    @mcp.tool(
        name="list_rooms",
        description=(
            "Враќа листа на простории (име, тип, локација) што ги задоволуваат "
            "зададените филтри (комбинирани со И). Сите филтри се опционални; "
            "резултатот е ограничен со `limit`. Детали за просторија: `get_room_data`."
        ),
        annotations=ToolAnnotations(
            title="Листа на простории по филтри",
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
            readOnlyHint=True,
        ),
    )
    @track_tool("list_rooms")
    async def list_rooms_tool(
        type: Annotated[
            RoomType | None,
            Field(
                description="Тип на просторијата.",
                examples=["Лабораторија", "Кабинет"],
            ),
        ] = None,
        location: Annotated[
            RoomLocation | None,
            Field(
                description="Локација на просторијата.",
                examples=["ТМФ", "Анекс на ФЕИТ"],
            ),
        ] = None,
        floor: Annotated[
            str | None,
            Field(
                description="Кат на просторијата.",
                examples=["0", "1", "-1"],
            ),
        ] = None,
        min_capacity: Annotated[
            int | None,
            Field(
                description="Минимален капацитет на просторијата.",
                ge=0,
                examples=[40],
            ),
        ] = None,
        *,
        query: Annotated[
            str | None,
            Field(
                description="Дел од името на просторијата (кирилица или латиница).",
                examples=["амфитеатар", "b2"],
                max_length=128,
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(description="Максимален број на простории.", ge=1, le=500),
        ] = DEFAULT_ROOM_LIMIT,
        offset: _Offset = 0,
    ) -> Annotated[CallToolResult, ListPage[RoomMatch]]:
        return compact_result(
            list_rooms(
                room_type=type,
                location=location,
                floor=floor,
                min_capacity=min_capacity,
                query=query,
                limit=limit,
                offset=offset,
            )
        )

    @mcp.tool(
        name="get_room_data",
        description=(
            "Враќа сите податоци за просторија: тип, локација, насоки, кат, "
            "капацитет и линк до MRBS распоред."
        ),
        annotations=ToolAnnotations(
            title="Податоци за просторија",
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
            readOnlyHint=True,
        ),
    )
    @track_tool("get_room_data")
    async def get_room_data_tool(
        name: Annotated[
            str,
            Field(
                description=(
                    "Име на просторијата. Совпаѓањето на името е толерантно (fuzzy) и "
                    "поддржува латиница; ако нема точно совпаѓање, враќа предлози."
                ),
                examples=["Ф10", "f10", "Б2.1", "b21", "amfiteatar"],
            ),
        ],
    ) -> RoomData:
        return get_room_data(name)

    @mcp.tool(
        name="list_staff",
        description=(
            "Враќа листа на вработени (наставен и ненаставен кадар) што ги "
            "задоволуваат зададените филтри (комбинирани со И). Сите филтри се "
            "опционални."
        ),
        annotations=ToolAnnotations(
            title="Листа на вработени по филтри",
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
            readOnlyHint=True,
        ),
    )
    @track_tool("list_staff")
    async def list_staff_tool(
        active: Annotated[
            bool | None,
            Field(
                description="Дали вработениот е активен или не (пензиониран).",
                examples=[True],
            ),
        ] = None,
        title: Annotated[
            StaffTitle | None,
            Field(
                description="Титула на вработениот.",
                examples=["д-р"],
            ),
        ] = None,
        position: Annotated[
            StaffPosition | None,
            Field(
                description="Позиција на вработениот.",
                examples=["Редовен професор"],
            ),
        ] = None,
    ) -> list[StaffMatch]:
        return list_staff(active=active, title=title, position=position)

    @mcp.tool(
        name="get_staff",
        description=(
            "Враќа вработен од FINKI Hub (Directus): титула, звање, е-пошта, кабинет, "
            "фотографија и линкови, институтот и функциите (деканатска управа, "
            "раководител на институт или центар, ННС), а со `include` и: `teaching` "
            "(предмети и неделни часови во најновиот главен распоред), `schedule` "
            "(неговите термини: ден, време, просторија, групи), `theses` (број на "
            "дипломски и магистерски по улога и најновите менторства), `programs` "
            "(програми што ги координира) и `bio` (биографија: образование, "
            "истражување). Вклучи само што ти треба."
        ),
        annotations=ToolAnnotations(
            title="Вработен со предмети, распоред и трудови",
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
            readOnlyHint=True,
        ),
    )
    @track_tool("get_staff")
    async def get_staff_tool(
        name: Annotated[
            str,
            Field(
                description=(
                    "Име на вработениот; толерантно совпаѓање, поддржува латиница. "
                    "Ако е нееднозначно, враќа предлози."
                ),
                examples=["Весна Димитрова", "vesna dimitrova"],
                max_length=256,
            ),
        ],
        include: Annotated[
            list[StaffInclude] | None,
            Field(
                description="Што да се вклучи: teaching, schedule, theses, programs, bio.",
                examples=[["teaching", "schedule"]],
            ),
        ] = None,
    ) -> Annotated[CallToolResult, StaffDetails]:
        details = await anyio.to_thread.run_sync(lambda: get_staff(name, include))
        return compact_result(details)

    @mcp.tool(
        name="get_leadership",
        description=(
            "Враќа тело на ФИНКИ од FINKI Hub (Directus): Деканатот (декан, "
            "продекани и секретар) или Факултетското студентско собрание (ФСС: "
            "претседател и членови), тековниот состав или составот во дадена година, "
            "со познатите години (мандати); или тековните: Деканатската управа "
            "(деканот, продеканите и раководителите на институтите), "
            "Наставно-научниот совет (ННС), институтите (раководител и членови) и "
            "центрите (раководител)."
        ),
        annotations=ToolAnnotations(
            title="Деканат, ННС, институти и студентско собрание",
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
            readOnlyHint=True,
        ),
    )
    @track_tool("get_leadership")
    async def get_leadership_tool(
        body: Annotated[
            LeadershipBody,
            Field(
                description=(
                    "„деканат“ (декан, продекани и секретар, по мандати), "
                    "„студентско собрание“ (ФСС), „деканатска управа“ (тековна, "
                    "деканот и продеканите со раководителите на институтите), „ннс“ "
                    "(Наставно-научен совет), „институти“ или „центри“."
                ),
                examples=["деканат"],
            ),
        ] = LeadershipBody.DEANS_OFFICE,
        year: Annotated[
            int | None,
            Field(
                description=(
                    "Година; составот што бил на функција тогаш. Без година: тековниот. "
                    "Само за деканатот и студентското собрание."
                ),
                examples=[2021],
                ge=2000,
                le=2100,
            ),
        ] = None,
    ) -> Annotated[CallToolResult, Leadership]:
        result = await anyio.to_thread.run_sync(lambda: get_leadership(body, year))
        return compact_result(result)

    @mcp.tool(
        name="get_course",
        description=(
            "Враќа предмет од FINKI Hub (Directus) по име или кратенка (на пр. „АПС“), "
            "а со `include` и: `curricula` (код, семестар, кредити, предуслови и "
            "статус по програма во секоја акредитација), `syllabus` (цели и содржина "
            "по недели), `equivalencies` (еквивалентни предмети низ акредитациите), "
            "`enrollments` (запишани по година), `teaching` (наставници од најновиот "
            "распоред во кој се држи), `schedule` (термини во тековниот распоред) и "
            "`programs` (магистерски програми во кои е, со вид, семестар и група) и "
            "`unlocks` (предмети за кои е предуслов, т.е. што може да се запише "
            "потоа). Опфаќа и магистерски предмети. Вклучи само што ти треба."
        ),
        annotations=ToolAnnotations(
            title="Предмет со акредитации, силабус и наставници",
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
            readOnlyHint=True,
        ),
    )
    @track_tool("get_course")
    async def get_course_tool(
        name: Annotated[
            str,
            Field(
                description=(
                    "Име или кратенка на предметот; толерантно совпаѓање, поддржува "
                    "латиница. Ако е нееднозначно, враќа предлози."
                ),
                examples=["Алгоритми и податочни структури", "АПС", "kriptografija"],
                max_length=256,
            ),
        ],
        include: Annotated[
            list[CourseInclude] | None,
            Field(
                description=(
                    "Што да се вклучи: curricula, syllabus, equivalencies, "
                    "enrollments, teaching, schedule, programs, unlocks."
                ),
                examples=[["curricula", "teaching"]],
            ),
        ] = None,
    ) -> Annotated[CallToolResult, CourseDetails]:
        details = await anyio.to_thread.run_sync(lambda: get_course(name, include))
        return compact_result(details)

    @mcp.tool(
        name="find_theses",
        description=(
            "Пребарува дипломски и магистерски трудови (Directus) по студент (име "
            "или индекс), вработен во комисијата и неговата улога (ментор, член, "
            "претседател), година и дел од насловот; најновите прво. Потребен е "
            "барем еден филтер. "
            "За целосни податоци за еден труд користи `get_diploma`/`get_master`."
        ),
        annotations=ToolAnnotations(
            title="Пребарување трудови по комисија, година и наслов",
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
            readOnlyHint=True,
        ),
    )
    @track_tool("find_theses")
    async def find_theses_tool(
        *,
        staff: Annotated[
            str | None,
            Field(
                description="Име на вработен во комисијата (ментор или член).",
                max_length=256,
            ),
        ] = None,
        student: Annotated[
            str | None,
            Field(
                description=(
                    "Студент: број на индекс или име (сите зборови, и на латиница)."
                ),
                max_length=256,
            ),
        ] = None,
        role: Annotated[
            ThesisRole | None,
            Field(
                description=(
                    "Улога на вработениот: mentor, member или president (само "
                    "магистерски); бара `staff`."
                ),
            ),
        ] = None,
        kind: Annotated[
            ThesisKind | None,
            Field(
                description="bachelor (дипломски) или master (магистерски); стандардно двата."
            ),
        ] = None,
        year: Annotated[
            int | None,
            Field(description="Година на трудот.", ge=2000, le=2100, examples=[2025]),
        ] = None,
        query: Annotated[
            str | None,
            Field(
                description="Дел од насловот (на писмото на насловот).",
                max_length=256,
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(description="Најмногу трудови во одговорот.", ge=1, le=100),
        ] = DEFAULT_THESIS_LIMIT,
    ) -> Annotated[CallToolResult, ThesisSearch]:
        result = await anyio.to_thread.run_sync(
            lambda: find_theses(
                kind=kind,
                staff=staff,
                student=student,
                role=role,
                year=year,
                query=query,
                limit=limit,
            ),
        )
        return compact_result(result)

    @mcp.tool(
        name="stats",
        description=(
            "Враќа статистика од FINKI Hub (Directus) како подредени редови: "
            "`top_courses` (предмети со најмногу запишани во академска година; "
            "стандардно најновата со податоци), `theses_per_year` (трудови по година, "
            "дипломски и магистерски; со `staff` неговите менторства), `top_mentors` "
            "(најмногу менторства, по `year` и `kind`) и `teaching_load` (неделни "
            "часови и број на предмети по наставник во тековниот распоред)."
        ),
        annotations=ToolAnnotations(
            title="Статистика: запишани, трудови, менторства, оптоварување",
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
            readOnlyHint=True,
        ),
    )
    @track_tool("stats")
    async def stats_tool(
        metric: Annotated[
            StatsMetric,
            Field(
                description=(
                    "top_courses, theses_per_year, top_mentors или teaching_load."
                ),
            ),
        ],
        *,
        academic_year: Annotated[
            str | None,
            Field(
                description="Академска година за `top_courses`, на пр. „2025/2026“.",
                pattern=r"^\d{4}/\d{4}$",
            ),
        ] = None,
        year: Annotated[
            int | None,
            Field(description="Година за `top_mentors`.", ge=2000, le=2100),
        ] = None,
        kind: Annotated[
            ThesisKind | None,
            Field(description="bachelor или master за трудовите; стандардно двата."),
        ] = None,
        staff: Annotated[
            str | None,
            Field(
                description="Вработен за `theses_per_year` (неговите менторства).",
                max_length=256,
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(description="Најмногу редови.", ge=1, le=50),
        ] = DEFAULT_STATS_LIMIT,
    ) -> Annotated[CallToolResult, Stats]:
        result = await anyio.to_thread.run_sync(
            lambda: stats(
                metric,
                academic_year=academic_year,
                year=year,
                kind=kind,
                staff=staff,
                limit=limit,
            ),
        )
        return compact_result(result)

    @mcp.tool(
        name="schedule",
        description=(
            "Враќа термини од најновиот главен распоред на ФИНКИ (Directus) за "
            "вработен, предмет, просторија и/или група, со можен ден. Филтрите се "
            "комбинираат со И; имињата се пронаоѓаат толерантно (и кратенки на "
            "предмети, на пр. „АПС“), а при нееднозначност враќа предлози. За "
            "постари или прво-неделни распореди користи ги `list_timetable_*`."
        ),
        annotations=ToolAnnotations(
            title="Распоред (кој, што, каде, кога)",
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
            readOnlyHint=True,
        ),
    )
    @track_tool("schedule")
    async def schedule_tool(
        staff: Annotated[
            str | None,
            Field(description="Име на вработен.", max_length=256),
        ] = None,
        course: Annotated[
            str | None,
            Field(description="Име или кратенка на предмет.", max_length=256),
        ] = None,
        room: Annotated[
            str | None,
            Field(
                description="Просторија, на пр. „Б2.2“ или „315 (ТМФ)“.",
                max_length=256,
            ),
        ] = None,
        group: Annotated[
            str | None,
            Field(
                description="Група од распоредот или нејзин почеток, на пр. „2г-КН“.",
                max_length=64,
            ),
        ] = None,
        day: Annotated[
            TimetableDay | None,
            Field(description="Ден во неделата.", examples=["Среда"]),
        ] = None,
    ) -> Annotated[CallToolResult, Schedule]:
        result = await anyio.to_thread.run_sync(
            lambda: schedule(
                staff=staff, course=course, room=room, group=group, day=day
            ),
        )
        return compact_result(result)

    @mcp.tool(
        name="get_diploma",
        description=(
            "Враќа податоци за дипломска работа по име на студент или број на индекс. "
            "При нееднозначно пребарување враќа предлози."
        ),
        annotations=ToolAnnotations(
            title="Податоци за дипломска работа",
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
            readOnlyHint=True,
        ),
    )
    @track_tool("get_diploma")
    async def get_diploma_tool(
        student: Annotated[
            str,
            Field(
                description=(
                    "Име на студент или број на индекс; името поддржува толерантно "
                    "совпаѓање и латиница."
                ),
                max_length=256,
            ),
        ],
    ) -> DiplomaResult:
        return await anyio.to_thread.run_sync(get_diploma, student)

    @mcp.tool(
        name="get_master",
        description=(
            "Враќа податоци за магистерски труд по име на студент или број на индекс. "
            "При нееднозначно пребарување враќа предлози."
        ),
        annotations=ToolAnnotations(
            title="Податоци за магистерски труд",
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
            readOnlyHint=True,
        ),
    )
    @track_tool("get_master")
    async def get_master_tool(
        student: Annotated[
            str,
            Field(
                description=(
                    "Име на студент или број на индекс; името поддржува толерантно "
                    "совпаѓање и латиница."
                ),
                max_length=256,
            ),
        ],
    ) -> MasterResult:
        return await anyio.to_thread.run_sync(get_master, student)

    @mcp.tool(
        name="search_announcements",
        description=(
            "Ги враќа најновите огласи од огласната табла на ФИНКИ (finki.ukim.mk): "
            "рокови за упис и заверка на семестар, пријавување испити, уписни рокови, "
            "конкурси, стипендии, промени во работно време. Користи ја за прашања за "
            "тековни рокови и датуми. Со `board` ги пребарува и настаните на ФИНКИ "
            "(„настани“) и огласите за работа и пракса („работа и пракса“). Секој "
            "резултат содржи наслов, датум, линк и извадок; за целиот текст користи "
            "get_announcement со истиот `board`."
        ),
        annotations=ToolAnnotations(
            title="Пребарување огласи од ФИНКИ",
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
            readOnlyHint=True,
        ),
    )
    @track_tool("search_announcements")
    async def search_announcements_tool(
        query: Annotated[
            str | None,
            Field(
                description=(
                    "Клучни зборови на македонски, со кирилица или латиница. Без "
                    "барање се враќаат најновите огласи."
                ),
                max_length=256,
                examples=["упис семестар", "пријава испити", "upis semestar"],
            ),
        ] = None,
        since: Annotated[
            date | None,
            Field(
                description=(
                    "Најстар датум на објавување (YYYY-MM-DD). Стандардно 180 дена "
                    "пред денешниот датум."
                ),
                examples=["2026-09-01"],
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(
                description="Максимален број на огласи.",
                ge=1,
                le=10,
                examples=[5],
            ),
        ] = 5,
        board: Annotated[
            Board,
            Field(
                description=(
                    "Која табла: „огласи“ (огласна табла), „настани“ (предавања, "
                    "натпревари, работилници и други настани) или „работа и пракса“ "
                    "(огласи за работа и пракса од компании)."
                ),
                examples=["настани"],
            ),
        ] = Board.ANNOUNCEMENTS,
    ) -> AnnouncementSearchResult:
        return await anyio.to_thread.run_sync(
            lambda: search_announcements(
                query=query, since=since, limit=limit, board=board
            ),
        )

    @mcp.tool(
        name="get_announcement",
        description=(
            "Го враќа целиот текст на оглас, настан или оглас за работа и пракса од "
            "ФИНКИ по ID (добиено од search_announcements, со истиот `board`), "
            "заедно со наслов, датум и линк."
        ),
        annotations=ToolAnnotations(
            title="Текст на оглас од ФИНКИ",
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
            readOnlyHint=True,
        ),
    )
    @track_tool("get_announcement")
    async def get_announcement_tool(
        id: Annotated[
            int,
            Field(
                description="ID на огласот.",
                ge=1,
                examples=[21653],
            ),
        ],
        board: Annotated[
            Board,
            Field(
                description=(
                    "Која табла: „огласи“ (огласна табла), „настани“ (предавања, "
                    "натпревари, работилници и други настани) или „работа и пракса“ "
                    "(огласи за работа и пракса од компании)."
                ),
                examples=["настани"],
            ),
        ] = Board.ANNOUNCEMENTS,
    ) -> AnnouncementDetail:
        return await anyio.to_thread.run_sync(get_announcement, id, board)

    return mcp


app = make_app(settings)


if __name__ == "__main__":
    app.run(
        transport="streamable-http",
        host=settings.HOST,
        port=settings.PORT,
    )
