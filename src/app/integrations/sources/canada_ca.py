"""Parser for Canada.ca pages: IRCC public guidance and program delivery instructions."""

import logging
import re
from dataclasses import dataclass, field
from datetime import date

from lxml import html

from app.domain.corpus import ParsedDocument, ParsedLink, ParsedSegment, Source
from app.domain.links import LinkResolver
from app.domain.refs import PAGE_INTRO_SLUG, page_ref, slugify

logger = logging.getLogger(__name__)

# Headings that start a segment, and how deep each one nests. Lower headings stay in the body.
HEADING_DEPTH = {"h2": 0, "h3": 1}
KIND = {0: "section", 1: "subsection"}
SKIPPED_TAGS = {"nav", "script", "style", "noscript", "template", "form", "button", "h1"}
# Page furniture inside <main>: invisible headings, the pager, and the "Page details" footer.
SKIPPED_CLASSES = {"wb-inv", "pagedetails", "mwspagination", "gc-subway"}
BLOCK_TAGS = {
    "p", "div", "section", "article", "ul", "ol", "table", "tr", "details", "summary", "dl",
    "dt", "dd", "h4", "h5", "h6", "blockquote", "figure", "figcaption", "caption", "br", "pre",
}  # fmt: skip
CELL_TAGS = {"td", "th"}
TABLE_OF_CONTENTS = "on this page"


@dataclass
class _Section:
    ref: str
    parent_ref: str | None
    kind: str
    depth: int
    slugs: tuple[str, ...]
    heading_path: tuple[str, ...]
    url: str
    anchor: str | None
    parts: list[str] = field(default_factory=list)
    links: list[ParsedLink] = field(default_factory=list)
    has_children: bool = False


def parse(source: Source, raw: bytes, resolver: LinkResolver) -> ParsedDocument:
    document = html.document_fromstring(raw, parser=html.HTMLParser(encoding="utf-8"))
    main = document.find(".//main")
    if main is None:
        raise ValueError("page has no <main> element")
    modified = document.xpath("string(//meta[@name='dcterms.modified']/@content)")
    modified_on = date.fromisoformat(modified) if modified else None

    builder = _Builder(source.slug, source.url, _title(document, source), resolver)
    builder.walk(main)
    if builder.has_ajax_content:
        logger.warning("%s: part of the page is loaded by script and was not captured", source.slug)

    segments = tuple(
        ParsedSegment(
            ref=section.ref,
            parent_ref=section.parent_ref,
            kind=section.kind,
            depth=section.depth,
            heading_path=section.heading_path,
            body=_clean(section.parts),
            url=section.url,
            last_amended_on=modified_on,
            anchor=section.anchor,
            links=tuple(section.links),
        )
        for section in builder.sections
    )
    # A heading with neither text nor subsections gives nothing to cite.
    kept = tuple(
        segment
        for segment, section in zip(segments, builder.sections, strict=True)
        if segment.body or section.has_children
    )
    return ParsedDocument(kept, modified_on)


def _title(document: html.HtmlElement, source: Source) -> str:
    for heading in document.xpath("//main//h1[@property='name']"):
        if text := _inline(heading):
            return text
    return document.xpath("string(//meta[@name='dcterms.title']/@content)").strip() or source.title


class _Builder:
    """Walks <main> in document order, cutting a new section at each h2 and h3."""

    def __init__(self, source_slug: str, page_url: str, title: str, resolver: LinkResolver) -> None:
        self._source_slug = source_slug
        self._page_url = page_url
        self._resolver = resolver
        self._title = title
        self._skipped: set[html.HtmlElement] = set()
        self._refs: set[str] = set()
        self.has_ajax_content = False
        # Text above the first heading belongs to the intro.
        self.sections = [self._section(None, PAGE_INTRO_SLUG, None, "intro", None)]

    def walk(self, element: html.HtmlElement, list_depth: int = 0) -> None:
        tag = element.tag
        if not isinstance(tag, str) or self._is_skipped(element):
            return
        if any(name.startswith("data-ajax-") for name in element.attrib):
            self.has_ajax_content = True
        if tag in HEADING_DEPTH:
            self._heading(element, HEADING_DEPTH[tag])
            return

        if tag == "a" and element.get("href"):
            link = self._resolver.html_link(self._page_url, element.get("href"), _inline(element))
            if link is not None:
                self.sections[-1].links.append(link)

        if tag == "li":
            self._emit("\n" + "  " * (list_depth - 1) + "- ")
        elif tag in CELL_TAGS:
            self._emit(" | ")
        elif tag in BLOCK_TAGS:
            self._emit("\n")
        self._emit(element.text)
        for child in element:
            self.walk(child, list_depth + (tag in ("ul", "ol")))
            self._emit(child.tail)
        if tag in BLOCK_TAGS:
            self._emit("\n")

    def _is_skipped(self, element: html.HtmlElement) -> bool:
        return (
            element.tag in SKIPPED_TAGS
            or element in self._skipped
            or not SKIPPED_CLASSES.isdisjoint(element.get("class", "").split())
        )

    def _heading(self, element: html.HtmlElement, depth: int) -> None:
        text = _inline(element)
        if text.lower() == TABLE_OF_CONTENTS:
            following = element.getnext()
            if following is not None and following.tag in ("ul", "ol"):
                self._skipped.add(following)
            return
        if not text:
            return
        # An h3 nests under the h2 before it. One with no h2 above it stands alone.
        parent = next((s for s in reversed(self.sections) if s.kind == KIND[0]), None)
        slug, anchor = slugify(text) or "section", element.get("id")
        if depth == 0 or parent is None:
            self.sections.append(self._section(None, slug, text, KIND[0], anchor))
        else:
            parent.has_children = True
            self.sections.append(self._section(parent, slug, text, KIND[1], anchor))

    def _section(
        self,
        parent: _Section | None,
        slug: str,
        heading: str | None,
        kind: str,
        anchor: str | None,
    ) -> _Section:
        parent_slugs = parent.slugs if parent else ()
        unique, n = slug, 1
        while page_ref(self._source_slug, (*parent_slugs, unique)) in self._refs:
            n += 1
            unique = f"{slug}-{n}"
        slugs = (*parent_slugs, unique)
        ref = page_ref(self._source_slug, slugs)
        self._refs.add(ref)
        path = parent.heading_path if parent else (self._title,)
        return _Section(
            ref=ref,
            parent_ref=parent.ref if parent else None,
            kind=kind,
            depth=len(slugs) - 1,
            slugs=slugs,
            heading_path=(*path, heading) if heading else path,
            # A heading with an id can be linked to directly; otherwise link to the page.
            url=f"{self._page_url}#{anchor}" if anchor else self._page_url,
            anchor=anchor,
        )

    def _emit(self, text: str | None) -> None:
        if text:
            self.sections[-1].parts.append(text)


def _inline(element: html.HtmlElement) -> str:
    return " ".join(element.text_content().split())


def _clean(parts: list[str]) -> str:
    """One line per block, list items as indented bullets, table cells joined by ' | '."""
    lines = []
    for line in "".join(parts).split("\n"):
        indent = re.match(r" *(?=- )", line)
        text = " ".join(line.split()).removeprefix("| ")
        if text and text != "-":
            lines.append((indent.group(0) if indent else "") + text)
    return "\n".join(lines)
