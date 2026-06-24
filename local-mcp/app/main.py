from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from app.schemas.committee import CommitteeRecommendation
from app.schemas.course_participants import ParticipantsData
from app.schemas.course_staff import StaffData
from app.tools.committee import recommend_committee
from app.tools.course_participants import (
    get_available_courses_for_participants,
    get_participants_for_course,
)
from app.tools.course_staff import (
    get_available_courses_for_staff,
    get_staff_for_course,
)
from app.utils.query_matcher import (
    match_query_to_candidates,
)
from app.utils.settings import Settings

settings = Settings()


def make_app(settings: Settings) -> FastMCP:
    mcp = FastMCP(
        port=settings.PORT,
        host=settings.HOST,
    )

    @mcp.custom_route("/health", methods=["GET", "HEAD"])
    async def health_check(request: Request) -> PlainTextResponse:
        return PlainTextResponse("OK")

    @mcp.tool(
        name="get_available_courses_with_staff_data",
        description="Get a list of available courses for staff.",
        annotations=ToolAnnotations(
            title="Get Available Courses for Staff",
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
            readOnlyHint=True,
        ),
    )
    async def get_available_courses_with_staff_data_tool() -> list[str]:
        result = get_available_courses_for_staff()

        return result

    @mcp.tool(
        name="get_staff_data_for_course",
        description="Get staff data for a specific course.",
        annotations=ToolAnnotations(
            title="Get Staff Data for Course",
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
            readOnlyHint=True,
        ),
    )
    async def get_staff_data_for_course_tool(course_name: str) -> StaffData:
        course_names = get_available_courses_for_staff()
        result = match_query_to_candidates(course_name, course_names)
        if result["match"]:
            staff_data = get_staff_for_course(result["match"])
            staff_data["match_info"] = {
                "original_query": course_name,
                "matched_course": result["match"],
                "similarity_score": result["score"],
                "match_type": result["match_type"],
            }
            return StaffData(**staff_data)

        suggestions = result.get("suggestions")
        if not isinstance(suggestions, list):
            suggestions = None

        return StaffData(
            course=course_name,
            professors=[],
            assistants=[],
            error=f"Course '{course_name}' not found",
            suggestions=suggestions,
            match_info=None,
        )

    @mcp.tool(
        name="get_available_courses_for_participants",
        description="Get a list of available courses for participants.",
        annotations=ToolAnnotations(
            title="Get Available Courses for Participants",
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
            readOnlyHint=True,
        ),
    )
    async def get_available_courses_for_participants_tool() -> list[str]:
        result = get_available_courses_for_participants()

        return result

    @mcp.tool(
        name="get_participants_for_course",
        description="Get participant counts for a specific course, with robust matching.",
        annotations=ToolAnnotations(
            title="Get Participants for Course",
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
            readOnlyHint=True,
        ),
    )
    async def get_participants_for_course_tool(course_name: str) -> ParticipantsData:
        course_names = get_available_courses_for_participants()
        result = match_query_to_candidates(course_name, course_names)
        suggestions = (
            result["suggestions"] if isinstance(result["suggestions"], list) else []
        )

        if result["match"]:
            participants_data = get_participants_for_course(result["match"])
            participants_data["match_info"] = {
                "original_query": course_name,
                "matched_course": result["match"],
                "similarity_score": result["score"],
                "match_type": result["match_type"],
            }
            participants_data.setdefault("error", None)
            participants_data.setdefault("suggestions", suggestions)

            return ParticipantsData(**participants_data)

        return ParticipantsData(
            course=course_name,
            error=f"Course '{course_name}' not found",
            suggestions=suggestions,
            match_info=None,
        )

    @mcp.tool(
        name="recommend_thesis_committee",
        description=(
            "Recommend a thesis committee for a proposed thesis title. Give the title alone "
            "to get a recommended mentor plus two members; include a known mentor to get just "
            "the two members. Grounded in past FINKI defenses and professor publications."
        ),
        annotations=ToolAnnotations(
            title="Recommend Thesis Committee",
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
            readOnlyHint=True,
        ),
    )
    async def recommend_thesis_committee_tool(
        title: str,
        mentor: str | None = None,
    ) -> CommitteeRecommendation:
        return await recommend_committee(title, mentor)

    return mcp


app = make_app(settings)
