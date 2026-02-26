from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser


_BREAK_TAGS = {"br", "p", "li"}
_BLOCK_TAGS = {"div", "ul", "ol", "tr", "table", "section", "article"}
_WHITESPACE_RE = re.compile(r"[ \t\f\v\u00a0]+")
_EXTRA_NEWLINES_RE = re.compile(r"\n{3,}")


class _HTMLStripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:  # noqa: ARG002
        if tag in _BREAK_TAGS:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _BREAK_TAGS or tag in _BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if data:
            self._chunks.append(data)

    def handle_entityref(self, name: str) -> None:
        self._chunks.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self._chunks.append(f"&#{name};")

    def get_data(self) -> str:
        return "".join(self._chunks)


def strip_html(html: str) -> str:
    """Convert HTML to plain text with normalized spacing/new lines."""

    if not html:
        return ""

    parser = _HTMLStripper()
    parser.feed(html)
    parser.close()

    text = unescape(parser.get_data())
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    normalized_lines = [_WHITESPACE_RE.sub(" ", line).strip() for line in text.split("\n")]
    text = "\n".join(normalized_lines)
    text = _EXTRA_NEWLINES_RE.sub("\n\n", text)
    return text.strip()
