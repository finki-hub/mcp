from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

import anyio
from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from app.schemas.anto import AntoQuote
from app.schemas.course import (
    AccreditationYear,
    Course,
    CourseMatch,
    CourseParticipants,
    CourseStaff,
    CourseStatus,
    CourseTag,
    StudyProgram,
)
from app.schemas.defense import DefenseMatch, DiplomaResult, MasterResult
from app.schemas.room import RoomData, RoomLocation, RoomMatch, RoomType
from app.schemas.session import ExamSessionScheduleFile
from app.schemas.staff import (
    StaffMatch,
    StaffMember,
    StaffPosition,
    StaffTitle,
)
from app.schemas.timetable import (
    TimetableDay,
    TimetableEntity,
    TimetableEntry,
    TimetableLessonType,
    TimetableSummary,
)
from app.tools.anto import get_random_anto_quote
from app.tools.course import (
    get_course_data,
    get_course_participants,
    get_course_staff,
    list_courses,
)
from app.tools.diploma import get_diploma, list_diplomas
from app.tools.master import get_master, list_masters
from app.tools.room import get_room_data, list_rooms
from app.tools.session import list_exam_session_schedules
from app.tools.staff import get_staff_member, list_staff
from app.tools.timetable import (
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

settings = Settings()


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
            "Враќа достапни датотеки со распореди за испитни сесии и колоквиумски недели. "
            "Секоја ставка содржи ознака на сесијата и линк за преземање."
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
    async def list_exam_session_schedules_tool() -> list[ExamSessionScheduleFile]:
        return list_exam_session_schedules()

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
            "Враќа листа на достапни распореди. Секоја ставка содржи ID, наслов, "
            "почетен датум и академска година."
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
    async def list_timetables_tool() -> list[TimetableSummary]:
        return list_timetables()

    @mcp.tool(
        name="list_timetable_groups",
        description=(
            "Враќа групи во распоред (означува година на студии и студиска програма). Секоја ставка содржи ID и име; ID може да се "
            "користи како `group_id` во `list_timetable_entries`."
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
    ) -> list[TimetableEntity]:
        return list_timetable_groups(id)

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
            "Враќа предмети во распоред. Секоја ставка содржи ID и име; ID може да се "
            "користи како `course_id` во `list_timetable_entries`."
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
    ) -> list[TimetableEntity]:
        return list_timetable_courses(id)

    @mcp.tool(
        name="list_timetable_entries",
        description=(
            "Враќа термини од распоред што ги задоволуваат зададените ID филтри "
            "(комбинирани со И). Мора да биде зададен барем еден од `group_id`, "
            "`professor_id`, `room_id` или `course_id`; инаку враќа празна листа."
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
                description="ID на предметот добиен од `list_timetable_courses`.",
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
            "Враќа листа на предмети што ги задоволуваат зададените филтри "
            "(комбинирани со И). Сите филтри се опционални. Програма, статус и "
            "семестар се проверуваат заедно во рамки на една акредитација; предметот "
            "се вклучува ако барем една акредитација ги исполнува."
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
                description="Студиска програма; само предмети што се нудат во неа.",
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
    ) -> list[CourseMatch]:
        return list_courses(
            program=program,
            status=status,
            semester=semester,
            accreditation=accreditation,
            tags=tags,
            professors=professors,
            assistants=assistants,
        )

    @mcp.tool(
        name="get_course_data",
        description=(
            "Враќа општи податоци за предмет: ознаки, Discord канал и податоци по "
            "акредитација (код, ниво, семестар, кредити, предуслов, статус по студиска "
            "програма)."
        ),
        annotations=ToolAnnotations(
            title="Општи податоци за предмет",
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
            readOnlyHint=True,
        ),
    )
    @track_tool("get_course_data")
    async def get_course_data_tool(
        course_name: Annotated[
            str,
            Field(
                description=(
                    "Име на предметот. Совпаѓањето на името е толерантно (fuzzy) и "
                    "поддржува латиница; ако нема точно совпаѓање, враќа предлози."
                ),
                examples=["Веб програмирање", "veb programiranje"],
            ),
        ],
    ) -> Course:
        return get_course_data(course_name)

    @mcp.tool(
        name="get_course_staff",
        description="Враќа наставен кадар (професори и асистенти) за предмет.",
        annotations=ToolAnnotations(
            title="Наставен кадар за предмет",
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
            readOnlyHint=True,
        ),
    )
    @track_tool("get_course_staff")
    async def get_course_staff_tool(
        course_name: Annotated[
            str,
            Field(
                description=(
                    "Име на предметот. Совпаѓањето на името е толерантно (fuzzy) и "
                    "поддржува латиница; ако нема точно совпаѓање, враќа предлози."
                ),
                examples=["Веб програмирање", "veb programiranje"],
            ),
        ],
    ) -> CourseStaff:
        return get_course_staff(course_name)

    @mcp.tool(
        name="get_course_participants",
        description="Враќа број на запишани студенти по академска година за предмет.",
        annotations=ToolAnnotations(
            title="Запишани студенти по предмет",
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
            readOnlyHint=True,
        ),
    )
    @track_tool("get_course_participants")
    async def get_course_participants_tool(
        course_name: Annotated[
            str,
            Field(
                description=(
                    "Име на предметот. Совпаѓањето на името е толерантно (fuzzy) и "
                    "поддржува латиница; ако нема точно совпаѓање, враќа предлози."
                ),
                examples=["Веб програмирање", "veb programiranje"],
            ),
        ],
    ) -> CourseParticipants:
        return get_course_participants(course_name)

    @mcp.tool(
        name="list_rooms",
        description=(
            "Враќа листа на простории што ги задоволуваат зададените филтри "
            "(комбинирани со И). Сите филтри се опционални."
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
    ) -> list[RoomMatch]:
        return list_rooms(
            type=type,
            location=location,
            floor=floor,
            min_capacity=min_capacity,
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
        name="get_staff_member",
        description=(
            "Враќа сите податоци за вработен: титула, звање, активност, е-пошта, "
            "кабинет и линкови до ФИНКИ профилот, Courses профилот и консултации."
        ),
        annotations=ToolAnnotations(
            title="Податоци за вработен",
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
            readOnlyHint=True,
        ),
    )
    @track_tool("get_staff_member")
    async def get_staff_member_tool(
        name: Annotated[
            str,
            Field(
                description=(
                    "Име на вработениот. Совпаѓањето на името е толерантно (fuzzy) и "
                    "поддржува латиница; ако нема точно совпаѓање, враќа предлози."
                ),
                examples=["Александар Стојменски", "aleksandar stojmenski"],
            ),
        ],
    ) -> StaffMember:
        return get_staff_member(name)

    @mcp.tool(
        name="list_diplomas",
        description=(
            "Враќа до 20 дипломски работи по студент, ментор или наслов. Потребен е "
            "барем еден непразен филтер; при пребарување со број на индекс не се "
            "задаваат други филтри, а другите филтри се комбинираат со И."
        ),
        annotations=ToolAnnotations(
            title="Листа на дипломски работи",
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
            readOnlyHint=True,
        ),
    )
    @track_tool("list_diplomas")
    async def list_diplomas_tool(
        student: Annotated[
            str | None,
            Field(
                description=(
                    "Име на студент или број на индекс; името поддржува толерантно "
                    "совпаѓање и латиница, а пребарувањето со број на индекс не се "
                    "комбинира со други филтри."
                ),
                max_length=256,
            ),
        ] = None,
        mentor: Annotated[
            str | None,
            Field(
                description="Име на менторот; поддржува толерантно совпаѓање и латиница.",
                max_length=256,
            ),
        ] = None,
        title: Annotated[
            str | None,
            Field(
                description="Наслов или дел од насловот на дипломската работа.",
                max_length=1024,
            ),
        ] = None,
    ) -> list[DefenseMatch]:
        return await anyio.to_thread.run_sync(
            lambda: list_diplomas(student=student, mentor=mentor, title=title),
        )

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
        name="list_masters",
        description=(
            "Враќа до 20 магистерски трудови по студент, ментор или наслов. Потребен "
            "е барем еден непразен филтер; при пребарување со број на индекс не се "
            "задаваат други филтри, а другите филтри се комбинираат со И."
        ),
        annotations=ToolAnnotations(
            title="Листа на магистерски трудови",
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
            readOnlyHint=True,
        ),
    )
    @track_tool("list_masters")
    async def list_masters_tool(
        student: Annotated[
            str | None,
            Field(
                description=(
                    "Име на студент или број на индекс; името поддржува толерантно "
                    "совпаѓање и латиница, а пребарувањето со број на индекс не се "
                    "комбинира со други филтри."
                ),
                max_length=256,
            ),
        ] = None,
        mentor: Annotated[
            str | None,
            Field(
                description="Име на менторот; поддржува толерантно совпаѓање и латиница.",
                max_length=256,
            ),
        ] = None,
        title: Annotated[
            str | None,
            Field(
                description="Наслов или дел од насловот на магистерскиот труд.",
                max_length=1024,
            ),
        ] = None,
    ) -> list[DefenseMatch]:
        return await anyio.to_thread.run_sync(
            lambda: list_masters(student=student, mentor=mentor, title=title),
        )

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

    return mcp


app = make_app(settings)


if __name__ == "__main__":
    app.run(
        transport="streamable-http",
        host=settings.HOST,
        port=settings.PORT,
    )
