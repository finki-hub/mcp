import re
import threading
import time
from dataclasses import dataclass, field
from datetime import date

import anyio
import httpx
import pytest

from app.main import make_app
from app.tools import announcement as announcement_tools
from app.tools.announcement import (
    MAX_TEXT_LENGTH,
    AnnouncementNotFoundError,
    excerpt,
    get_announcement,
    search_announcements,
)
from app.utils import announcements_client
from app.utils.announcements_client import (
    AnnouncementSnapshotCache,
    AnnouncementsUnavailableError,
)
from app.utils.html_text import html_to_text
from app.utils.settings import Settings

_TODAY = date(2026, 10, 24)
_API_URL = Settings().FINKI_ANNOUNCEMENTS_API_URL


def _post(
    id: int,
    published: str,
    title: str,
    content: str,
    modified: str | None = None,
) -> dict[str, object]:
    return {
        "id": id,
        "date": f"{published}T10:00:00",
        "modified": f"{modified or published}T10:00:00",
        "link": f"https://finki.ukim.mk/announcements/post-{id}/",
        "title": {"rendered": title},
        "content": {"rendered": content},
    }


_ORIGINAL = _post(
    21633,
    "2026-09-15",
    "Заверка на летен и упис на зимски семестар 2026/2027",
    "<p>Почитувани студенти,</p>\n<p>Заверката на летниот и запишувањето на "
    "зимскиот семестар ќе се одвива <b>од 14.09.2026 до 17.09.2026</b>.</p>\n",
)
_EXTENSION = _post(
    21653,
    "2026-09-17",
    "Продолжување на рокот за заверка на летен и упис на зимски семестар 2026/2027",
    "<p>Почитувани студенти,</p>\n<p>Заверката на летниот и запишувањето на "
    "зимскиот семестар е продолжено до 19.09.2026.</p>\n",
)
_EXAMS = _post(
    21500,
    "2026-08-20",
    "Пријавување на испити од септемвриска испитна сесија",
    "<p>Пријавувањето на испитите ќе се одвива до 25.08.2026.</p>",
    modified="2026-08-22",
)
_GRANT = _post(
    21744,
    "2026-10-17",
    "Повик за Spark 2026 &#8211; до 30.000 евра",
    "<p>Повик за студенти &amp; алумни.</p>",
)
_OLD_ENROLLMENT = _post(
    17409,
    "2026-02-25",
    "Упис на летен семестар 2025/2026 за прв циклус студии",
    "<p>Уписот на летниот семестар трае до 06.03.2026.</p>",
)


@dataclass
class _FakeUpstream:
    pages: list[list[dict[str, object]]]
    remote: list[dict[str, object]] = field(default_factory=list)
    by_id: dict[int, dict[str, object]] = field(default_factory=dict)
    failing: bool = False
    search_calls: list[dict[str, str | int]] = field(default_factory=list)
    detail_calls: list[str] = field(default_factory=list)

    def __call__(self, url: str, params: dict[str, str | int]) -> object:
        if self.failing:
            raise httpx.ConnectError("upstream down")
        if "search" in params:
            self.search_calls.append(params)
            return self.remote
        if url != _API_URL:
            self.detail_calls.append(url)
            post_id = int(url.rsplit("/", 1)[1])
            if post_id not in self.by_id:
                request = httpx.Request("GET", url)
                raise httpx.HTTPStatusError(
                    "not found",
                    request=request,
                    response=httpx.Response(404, request=request),
                )
            return self.by_id[post_id]
        page = int(params["offset"]) // int(params["per_page"])
        return self.pages[page] if page < len(self.pages) else []


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        announcements_client,
        "_snapshot_cache",
        AnnouncementSnapshotCache(),
    )
    monkeypatch.setattr(announcement_tools, "_today", lambda: _TODAY)


def _use(monkeypatch: pytest.MonkeyPatch, upstream: _FakeUpstream) -> _FakeUpstream:
    monkeypatch.setattr(announcements_client, "_get_json", upstream)
    return upstream


def _snapshot(*posts: dict[str, object]) -> _FakeUpstream:
    return _FakeUpstream(pages=[list(posts)])


def test_html_to_text_strips_markup_and_decodes_entities() -> None:
    markup = (
        '<div class="x"><p>Почитувани студенти,</p>\n<p>Рок&nbsp;до <b>19.09.2026</b>'
        " &#8211; ФИНКИ &amp;#8211; крај</p><ul>\n<li>прво</li>\n<li><p>второ</p></li>"
        "</ul><script>alert(1)</script></div>"
    )

    assert html_to_text(markup) == (
        "Почитувани студенти,\nРок до 19.09.2026 – ФИНКИ – крај\n- прво\n- второ"
    )


def test_titles_are_decoded(monkeypatch: pytest.MonkeyPatch) -> None:
    _use(monkeypatch, _snapshot(_GRANT))

    (match,) = search_announcements().announcements

    assert match.title == "Повик за Spark 2026 – до 30.000 евра"
    assert match.excerpt == "Повик за студенти & алумни."


def test_latin_query_finds_cyrillic_post(monkeypatch: pytest.MonkeyPatch) -> None:
    _use(monkeypatch, _snapshot(_GRANT, _ORIGINAL))

    result = search_announcements(query="upis semestar")

    assert [match.id for match in result.announcements] == [21633]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("пријавување испити", 21500),
        ("испит", 21500),
        ("запишување семестар", 21633),
        ("уписот", 21633),
    ],
)
def test_inflected_queries_match(
    monkeypatch: pytest.MonkeyPatch, query: str, expected: int
) -> None:
    _use(monkeypatch, _snapshot(_GRANT, _ORIGINAL, _EXAMS))

    result = search_announcements(query=query)

    assert result.announcements[0].id == expected


def test_since_filters_older_posts(monkeypatch: pytest.MonkeyPatch) -> None:
    _use(monkeypatch, _snapshot(_GRANT, _ORIGINAL, _EXAMS, _OLD_ENROLLMENT))

    recent = search_announcements(query="упис", since=date(2026, 9, 1))
    default = search_announcements(query="упис")
    everything = search_announcements(query="упис", since=date(2026, 1, 1))

    assert [match.id for match in recent.announcements] == [21633]
    assert [match.id for match in default.announcements] == [21633]
    assert [match.id for match in everything.announcements] == [21633, 17409]


_SINGLE_PARENT = _post(
    21726,
    "2026-10-07",
    "Интерен Оглас – за избор на студенти чие родителско право го врши само еден "
    "родител, кои се стекнуваат со право на плаќање на половина од партиципацијата",
    "<p>Пријавата со потребните документи се поднесува до 20.10.2026. Пријавените "
    "студенти треба да имаат положени испитисо просечна оценка над 8,00.</p>",
)
_ADMITTED = _post(
    21684,
    "2026-09-29",
    "Пријавени кандидати и решение за прием за третиот уписен рок",
    "<p>Листа на кандидати примени на прв циклус студии.</p>",
)
_HACKATHON = _post(
    21744,
    "2026-10-17",
    "Повик за студентски хакатон",
    "<p>Пријавувањето на тимовите е отворено до 30.10.2026.</p>",
)
_OLD_EXAMS = _post(
    17457,
    "2025-05-21",
    "Пријавување на испити од јунска испитна сесија",
    "<p>Пријавувањето ќе се одвива до 03.6.2025</p>",
)


@pytest.mark.parametrize("query", ["пријавување испити", "prijavuvanje ispiti"])
def test_stem_only_body_matches_do_not_rank(
    monkeypatch: pytest.MonkeyPatch, query: str
) -> None:
    _use(monkeypatch, _snapshot(_SINGLE_PARENT, _ADMITTED, _HACKATHON, _EXAMS))

    result = search_announcements(query=query)

    assert [match.id for match in result.announcements][:1] == [21500]
    assert 21726 not in {match.id for match in result.announcements}
    assert 21684 not in {match.id for match in result.announcements}


def test_default_window_reaches_older_title_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use(monkeypatch, _snapshot(_SINGLE_PARENT, _HACKATHON, _OLD_EXAMS))

    default = search_announcements(query="пријавување испити")
    explicit = search_announcements(
        query="пријавување испити",
        since=date(2026, 5, 1),
    )

    assert [match.id for match in default.announcements] == [17457, 21744]
    assert [match.id for match in explicit.announcements] == [21744]


def test_title_match_in_window_keeps_default_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use(monkeypatch, _snapshot(_EXAMS, _OLD_EXAMS))

    result = search_announcements(query="пријавување испити")

    assert [match.id for match in result.announcements] == [21500]


def test_single_term_query_keeps_stem_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    scholarship = _post(
        21700,
        "2026-10-01",
        "Конкурс за стипендија за постдипломски студии",
        "<p>Рок за аплицирање: 15.11.2026.</p>",
    )
    _use(monkeypatch, _snapshot(_GRANT, scholarship))

    result = search_announcements(query="стипендии")

    assert [match.id for match in result.announcements] == [21700]


def test_limit_caps_results(monkeypatch: pytest.MonkeyPatch) -> None:
    _use(monkeypatch, _snapshot(_GRANT, _ORIGINAL, _EXAMS, _EXTENSION))

    assert len(search_announcements(limit=2).announcements) == 2
    assert [match.id for match in search_announcements(limit=1).announcements] == [
        21744
    ]


def test_limit_bounds_are_declared_on_the_tool() -> None:
    tools = anyio.run(make_app(Settings()).list_tools)
    (tool,) = [tool for tool in tools if tool.name == "search_announcements"]
    limit = tool.input_schema["properties"]["limit"]

    assert (limit["minimum"], limit["maximum"], limit["default"]) == (1, 10, 5)
    assert tool.annotations is not None
    assert tool.annotations.read_only_hint is True
    assert tool.annotations.open_world_hint is True


def test_newer_extension_outranks_original(monkeypatch: pytest.MonkeyPatch) -> None:
    _use(monkeypatch, _snapshot(_GRANT, _ORIGINAL, _EXTENSION))

    result = search_announcements(query="заверка семестар")

    assert [match.id for match in result.announcements] == [21653, 21633]
    assert result.announcements[0].published == date(2026, 9, 17)


def test_updated_is_only_set_when_modified(monkeypatch: pytest.MonkeyPatch) -> None:
    _use(monkeypatch, _snapshot(_ORIGINAL, _EXAMS))

    by_id = {match.id: match for match in search_announcements().announcements}

    assert by_id[21500].updated == date(2026, 8, 22)
    assert by_id[21633].updated is None
    assert "updated" not in by_id[21633].model_dump()


def test_failed_refresh_serves_stale_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        announcements_client,
        "_snapshot_cache",
        AnnouncementSnapshotCache(ttl=0, retry_delay=0, background=False),
    )
    upstream = _use(monkeypatch, _snapshot(_ORIGINAL))
    fresh = search_announcements()

    upstream.failing = True
    stale = search_announcements()

    assert fresh.stale is False
    assert stale.stale is True
    assert stale.fetched_at == fresh.fetched_at
    assert [match.id for match in stale.announcements] == [21633]


def test_expired_snapshot_is_served_while_refreshing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        announcements_client,
        "_snapshot_cache",
        AnnouncementSnapshotCache(ttl=0, retry_delay=0),
    )
    _use(monkeypatch, _snapshot(_ORIGINAL))
    search_announcements()

    release = threading.Event()
    newer = _snapshot(_ORIGINAL, _EXTENSION)

    def slow_upstream(url: str, params: dict[str, str | int]) -> object:
        release.wait(timeout=5)
        return newer(url, params)

    monkeypatch.setattr(announcements_client, "_get_json", slow_upstream)

    started = time.monotonic()
    while_refreshing = search_announcements()
    elapsed = time.monotonic() - started
    release.set()
    deadline = time.monotonic() + 5
    while len(search_announcements().announcements) < 2:
        assert time.monotonic() < deadline
        time.sleep(0.01)

    assert elapsed < 1
    assert [match.id for match in while_refreshing.announcements] == [21633]
    assert while_refreshing.stale is False


def test_cold_failure_raises_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    _use(monkeypatch, _FakeUpstream(pages=[], failing=True))

    with pytest.raises(AnnouncementsUnavailableError) as error:
        search_announcements(query="упис")

    assert str(error.value) == "Огласната табла моментално не е достапна."


def test_excerpt_never_cuts_a_date() -> None:
    filler = " ".join(["студентите"] * 60)
    middle = " ".join(["студентите"] * 16)
    # Shift the date across the end of the 400-character window around the hit.
    for padding in range(1, 50):
        text = f"{filler} упис {'б' * padding} {middle} 19. 09. 2026 година. {filler}"
        snippet = excerpt(text, ["упис"])
        parts = re.findall(r"\d+", snippet)

        assert "упис" in snippet
        assert parts in ([], ["19", "09", "2026"]), snippet


def test_excerpt_centres_on_hit_and_opening_without_query() -> None:
    filler = " ".join(["информации"] * 80)
    text = f"Почитувани студенти, {filler} Рокот за упис е до 19.09.2026. {filler}"

    assert "Рокот за упис е до 19.09.2026." in excerpt(text, ["упис"])
    assert excerpt(text, []).startswith("Почитувани студенти,")
    assert len(excerpt(text, ["упис"])) <= 402


def test_get_announcement_caps_text(monkeypatch: pytest.MonkeyPatch) -> None:
    paragraphs = "".join(f"<p>Ред {index} {'текст ' * 20}</p>" for index in range(200))
    long_post = _post(21590, "2026-09-04", "Подготвителна настава", paragraphs)
    _use(monkeypatch, _snapshot(long_post))

    detail = get_announcement(21590)

    assert detail.truncated is True
    assert len(detail.text) <= MAX_TEXT_LENGTH + 2
    assert detail.text.startswith("Ред 0 текст")
    assert detail.title == "Подготвителна настава"
    assert detail.published == date(2026, 9, 4)
    assert detail.url == "https://finki.ukim.mk/announcements/post-21590/"


def test_get_announcement_fetches_missing_posts_by_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upstream = _use(monkeypatch, _snapshot(_GRANT))
    upstream.by_id[17457] = _post(
        17457,
        "2025-05-21",
        "Пријавување на испити од јунска испитна сесија",
        "<p>Пријавувањето ќе се одвива до 03.6.2025</p>",
    )

    detail = get_announcement(17457)

    assert detail.text == "Пријавувањето ќе се одвива до 03.6.2025"
    assert detail.truncated is False
    assert upstream.detail_calls == [f"{_API_URL}/17457"]
    with pytest.raises(AnnouncementNotFoundError):
        get_announcement(1)


def test_fallback_search_skipped_when_snapshot_covers_since(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upstream = _use(monkeypatch, _snapshot(_GRANT, _OLD_ENROLLMENT))

    search_announcements(query="испити", since=date(2026, 3, 1))

    assert upstream.search_calls == []


def test_fallback_search_skipped_when_enough_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upstream = _use(monkeypatch, _snapshot(_ORIGINAL, _EXTENSION))

    search_announcements(query="семестар", since=date(2025, 1, 1), limit=2)

    assert upstream.search_calls == []


def test_fallback_search_used_for_older_posts(monkeypatch: pytest.MonkeyPatch) -> None:
    old_exams = _post(
        17457,
        "2025-05-21",
        "Пријавување на испити од јунска испитна сесија",
        "<p>Пријавувањето ќе се одвива до 03.6.2025</p>",
    )
    upstream = _use(monkeypatch, _snapshot(_GRANT, _ORIGINAL))
    upstream.remote = [old_exams]

    result = search_announcements(query="prijavuvanje ispiti", since=date(2025, 1, 1))

    assert [match.id for match in result.announcements] == [17457]
    (call,) = upstream.search_calls
    assert call["search"] == "пријавување испити"
    assert call["after"] == "2025-01-01T00:00:00"
