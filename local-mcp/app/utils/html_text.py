from html import unescape
from html.parser import HTMLParser
from typing import Final

_BLOCK_TAGS: Final = frozenset(
    {
        "address",
        "article",
        "blockquote",
        "br",
        "dd",
        "div",
        "dl",
        "dt",
        "figcaption",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "li",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "tr",
        "ul",
    },
)
_CELL_TAGS: Final = frozenset({"td", "th"})
_SKIPPED_TAGS: Final = frozenset({"script", "style"})


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0
        self._pending_bullet = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIPPED_TAGS:
            self._skip_depth += 1
        elif tag in _BLOCK_TAGS:
            self._parts.append("\n")
            if tag == "li":
                self._pending_bullet = True
        elif tag in _CELL_TAGS:
            self._parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIPPED_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in _BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._pending_bullet and data.strip():
            self._parts.append("- ")
            self._pending_bullet = False
        # Source newlines are plain whitespace in HTML; only block tags break lines.
        self._parts.append(data.replace("\r", " ").replace("\n", " "))

    def text(self) -> str:
        lines = (" ".join(line.split()) for line in "".join(self._parts).splitlines())
        return "\n".join(line for line in lines if line)


def html_to_text(markup: str) -> str:
    """
    Convert rendered HTML to plain text, keeping paragraphs and list items on
    their own lines.
    """
    parser = _TextExtractor()
    parser.feed(markup)
    parser.close()
    # WordPress sometimes double-encodes entities such as &amp;#8211;.
    return unescape(parser.text())
