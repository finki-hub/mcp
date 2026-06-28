from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from app.schemas.committee import CommitteeRecommendation
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
from app.schemas.staff import (
    StaffMatch,
    StaffMember,
    StaffPosition,
    StaffTitle,
)
from app.tools.committee import recommend_committee
from app.tools.course import (
    get_course_data,
    get_course_participants,
    get_course_staff,
    list_courses,
)
from app.tools.staff import get_staff_member, list_staff
from app.utils.analytics import (
    capture_lifecycle_event,
    init_analytics,
    shutdown_analytics,
    track_tool,
)
from app.utils.settings import Settings

settings = Settings()


def make_app(settings: Settings) -> FastMCP:
    @asynccontextmanager
    async def lifespan(_server: FastMCP) -> AsyncIterator[None]:
        init_analytics(settings)
        tools = await _server.list_tools()
        capture_lifecycle_event("server_started", properties={"tool_count": len(tools)})
        try:
            yield
        finally:
            capture_lifecycle_event("server_stopped")
            shutdown_analytics()

    mcp = FastMCP(
        port=settings.PORT,
        host=settings.HOST,
        lifespan=lifespan,
    )

    @mcp.custom_route("/health", methods=["GET", "HEAD"])
    async def health_check(request: Request) -> PlainTextResponse:
        return PlainTextResponse("OK")

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
                description="Ознаки (тагови); предметот мора да ги содржи сите наведени.",
                examples=[["ai"]],
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
        name="recommend_thesis_committee",
        description=(
            "Препорачува комисија за дипломска работа според предложениот наслов. Доколку е "
            "даден само насловот, враќа препорачан ментор и двајца членови; доколку е наведен "
            "и менторот, враќа само двајцата членови. Се заснова на претходните одбрани на "
            "ФИНКИ и на трудовите на професорите."
        ),
        annotations=ToolAnnotations(
            title="Препорака на комисија за дипломска",
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
            readOnlyHint=True,
        ),
    )
    @track_tool("recommend_thesis_committee")
    async def recommend_thesis_committee_tool(
        title: str,
        mentor: str | None = None,
    ) -> CommitteeRecommendation:
        return await recommend_committee(title, mentor)

    return mcp


app = make_app(settings)
