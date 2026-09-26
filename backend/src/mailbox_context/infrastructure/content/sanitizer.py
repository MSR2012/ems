"""Server-side normalization of untrusted email content (§9, §20.3).

- HTML is sanitized with nh3 using an allow-list; scripts, event handlers, iframes, forms,
  `javascript:` URLs and CSS `url()` are removed.
- Remote images are blocked by default: `src` pointing to http(s) is dropped (only inline
  `data:`/`cid:` images survive), so rendering never contacts trackers.
- Plain text is extracted from HTML when no text part exists; malformed HTML falls back to text.
"""

from __future__ import annotations

import html as html_lib
import logging
import re
from html.parser import HTMLParser

import nh3

from mailbox_context.application.ports import ProcessedContent

logger = logging.getLogger(__name__)

MAX_HTML = 500_000
MAX_TEXT = 200_000

ALLOWED_TAGS = {
    "a", "abbr", "b", "blockquote", "br", "caption", "center", "code", "col", "colgroup", "dd",
    "div", "dl", "dt", "em", "font", "h1", "h2", "h3", "h4", "h5", "h6", "hr", "i", "img", "li",
    "ol", "p", "pre", "s", "small", "span", "strike", "strong", "sub", "sup", "table", "tbody",
    "td", "tfoot", "th", "thead", "tr", "u", "ul",
}
_COMMON = {"align", "valign", "width", "height", "style", "dir", "title", "bgcolor", "color"}
ALLOWED_ATTRIBUTES = {
    "*": {"style", "title", "dir", "align"},
    "a": {"href", "name", "target"},
    "img": {"src", "alt", "width", "height", "style"},
    "table": _COMMON | {"border", "cellpadding", "cellspacing"},
    "td": _COMMON | {"colspan", "rowspan"},
    "th": _COMMON | {"colspan", "rowspan"},
    "tr": _COMMON,
    "font": {"color", "face", "size"},
    "col": {"span", "width"},
    "colgroup": {"span", "width"},
}
_UNSAFE_CSS = re.compile(r"url\s*\(|expression\s*\(|@import|javascript:|behavior\s*:", re.I)
_REMOTE = re.compile(r"^\s*(https?:)?//", re.I)


class _Counter:
    def __init__(self) -> None:
        self.blocked = 0


def _attribute_filter(counter: _Counter):
    def f(element: str, attribute: str, value: str) -> str | None:
        if attribute == "style" and _UNSAFE_CSS.search(value):
            return None
        if element == "img" and attribute == "src":
            if _REMOTE.match(value) or not value.lower().startswith(("data:image/", "cid:")):
                counter.blocked += 1
                return None
        if attribute == "href" and value.strip().lower().startswith(("javascript:", "data:", "vbscript:")):
            return None
        return value
    return f


class _TextExtractor(HTMLParser):
    BLOCK = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table", "blockquote"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head", "title"):
            self._skip += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head", "title") and self._skip:
            self._skip -= 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)

    def text(self) -> str:
        raw = "".join(self.parts)
        lines = [re.sub(r"[ \t ]+", " ", ln).strip() for ln in raw.splitlines()]
        return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # noqa: BLE001
        return re.sub(r"<[^>]+>", " ", html)
    return parser.text()


def sanitize_html(html: str) -> tuple[str, int]:
    counter = _Counter()
    cleaned = nh3.clean(
        html[:MAX_HTML],
        tags=ALLOWED_TAGS,
        clean_content_tags={"script", "style", "iframe", "object", "embed", "form", "noscript",
                            "textarea", "select", "svg", "math", "template"},
        attributes=ALLOWED_ATTRIBUTES,
        attribute_filter=_attribute_filter(counter),
        url_schemes={"http", "https", "mailto", "cid", "data"},
        link_rel="noopener noreferrer nofollow",
        strip_comments=True,
    )
    return cleaned, counter.blocked


class NH3ContentProcessor:
    def process(self, *, html: str, text: str) -> ProcessedContent:
        html = html or ""
        text = (text or "").replace("\r\n", "\n")
        sanitized, blocked = "", 0
        if html.strip():
            try:
                sanitized, blocked = sanitize_html(html)
            except Exception:  # malformed HTML → fall back to plain text
                logger.warning("html sanitization failed; falling back to text")
                sanitized = ""
            if not text.strip():
                text = html_to_text(sanitized or html_lib.escape(html))
        return ProcessedContent(text=text[:MAX_TEXT], sanitized_html=sanitized,
                                remote_images_blocked=blocked)
