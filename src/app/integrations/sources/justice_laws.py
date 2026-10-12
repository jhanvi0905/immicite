"""Parser for the Justice Laws consolidated XML (laws-lois.justice.gc.ca/eng/XML/).

Citation links go to the site's reading pages: one page per section, where each provision
is anchored by the same `lims:id` it has in the XML.
"""

from datetime import date

from lxml import etree

from app.domain.corpus import ParsedDocument, ParsedLink, ParsedSegment, Source
from app.domain.links import LinkResolver
from app.domain.refs import definition_ref, law_ref, schedule_ref

LIMS = "{http://justice.gc.ca/lims}"

# Elements that become their own segment, and the kind each one gets.
STRUCTURAL = {
    "Section": "section",
    "Subsection": "subsection",
    "Paragraph": "paragraph",
    "Subparagraph": "subparagraph",
    "Clause": "clause",
    "Subclause": "subclause",
    "Definition": "definition",
}
# Children that are not part of a provision's text.
NOT_BODY = {"Label", "MarginalNote", "HistoricalNote"}
# Elements whose content is running text even when it holds only inline children.
ALWAYS_INLINE = {"Text", "Label", "MarginalNote", "TitleText"}


def parse(source: Source, raw: bytes, resolver: LinkResolver) -> ParsedDocument:
    root = etree.fromstring(raw, etree.XMLParser(resolve_entities=False, no_network=True))
    prefix = source.ref_prefix
    segments: list[ParsedSegment] = []

    # Only Body and the numbered schedules are law in force. The file also carries
    # RecentAmendments and "amending" schedules (related provisions, amendments not in force).
    headings: list[tuple[int, str]] = []
    for element in root.find("Body"):
        if element.tag == "Heading":
            level = int(element.get("level", "1"))
            headings = [h for h in headings if h[0] < level] + [(level, _heading_text(element))]
        elif element.tag == "Section":
            path = tuple(text for _, text in headings)
            walk = _Walk(source, resolver, _amended_on(element), segments)
            walk(element, prefix, None, 0, path, "")

    for schedule in root.findall("Schedule"):
        segment = _schedule(schedule, source, resolver)
        if segment is not None:
            segments.append(segment)

    _check_unique(segments)
    return ParsedDocument(tuple(segments), _date(root.get(f"{LIMS}lastAmendedDate")))


class _Walk:
    """Emits a section and everything under it, parents before children."""

    def __init__(
        self,
        source: Source,
        resolver: LinkResolver,
        amended_on: date | None,
        out: list[ParsedSegment],
    ) -> None:
        self._source = source
        self._resolver = resolver
        self._amended_on = amended_on
        self._out = out

    def __call__(
        self,
        element: etree._Element,
        parent_ref: str,
        parent_segment_ref: str | None,
        depth: int,
        heading_path: tuple[str, ...],
        section_url: str,
    ) -> None:
        source, language = self._source, self._source.language
        ref = _ref(element, parent_ref, language)
        anchor = element.get(f"{LIMS}id")
        if element.tag == "Section":
            url = section_url = f"{source.web_url}section-{_text(element.find('Label'))}.html"
        else:
            url = f"{section_url}#{anchor}" if anchor else section_url
        note = element.find("MarginalNote")
        if note is not None:
            heading_path += (_text(note),)
        elif element.tag == "Definition":
            heading_path += (_defined_term(element, language),)

        body: list[str] = []
        links: list[ParsedLink] = []
        children: list[etree._Element] = []
        for child in element:
            if child.tag in NOT_BODY:
                continue
            if child.tag in STRUCTURAL and _ref(child, ref, language) is not None:
                children.append(child)
            else:
                # Running text, tables, formulas, and provisions with nothing to address them by.
                body.append(_text(child))
                links.extend(_links(child, source, self._resolver))

        self._out.append(
            ParsedSegment(
                ref=ref,
                parent_ref=parent_segment_ref,
                kind=STRUCTURAL[element.tag],
                depth=depth,
                heading_path=heading_path,
                body="\n".join(part for part in body if part),
                url=url,
                last_amended_on=self._amended_on,
                anchor=anchor,
                links=tuple(links),
            )
        )
        for child in children:
            self(child, ref, ref, depth + 1, heading_path, section_url)


def _links(element: etree._Element, source: Source, resolver: LinkResolver) -> list[ParsedLink]:
    """Cross-references the XML tags explicitly. Plain-text ones are not extracted yet."""
    links = []
    for xref in element.iter("XRefInternal", "XRefExternal"):
        if xref.tag == "XRefInternal":
            link = resolver.section_xref(source, _text(xref), xref.tail or "")
        else:
            link = resolver.law_xref(
                xref.get("reference-type", ""), xref.get("link", ""), _text(xref)
            )
        if link is not None:
            links.append(link)
    return links


def _ref(element: etree._Element, parent_ref: str, language: str) -> str | None:
    if element.tag == "Definition":
        term = _defined_term(element, language)
        return definition_ref(parent_ref, term) if term else None
    label = element.find("Label")
    label_text = _text(label) if label is not None else ""
    if not label_text:
        if element.tag == "Section":
            raise ValueError(f"section without a label under {parent_ref!r}")
        return None
    return law_ref(parent_ref, label_text)


def _defined_term(element: etree._Element, language: str) -> str:
    term = element.find(f".//DefinedTerm{'Fr' if language == 'fr' else 'En'}")
    return _text(term) if term is not None else ""


def _schedule(
    schedule: etree._Element, source: Source, resolver: LinkResolver
) -> ParsedSegment | None:
    heading = schedule.find("ScheduleFormHeading")
    label = heading.find("Label") if heading is not None else None
    if label is None or heading.get("type") == "amending":
        return None
    return ParsedSegment(
        ref=schedule_ref(source.ref_prefix, _text(label)),
        parent_ref=None,
        kind="schedule",
        depth=0,
        heading_path=(_heading_text(heading),),
        body="\n".join(filter(None, (_text(c) for c in schedule if c is not heading))),
        # Schedules have no page of their own that can be derived, so link to the law.
        url=source.web_url,
        last_amended_on=_amended_on(schedule),
        anchor=schedule.get(f"{LIMS}id"),
        links=tuple(
            link for c in schedule if c is not heading for link in _links(c, source, resolver)
        ),
    )


def _heading_text(heading: etree._Element) -> str:
    parts = [
        _text(heading.find(tag)) for tag in ("Label", "TitleText") if heading.find(tag) is not None
    ]
    return " — ".join(part for part in parts if part)


def _amended_on(element: etree._Element) -> date | None:
    # Amendment dates exist on sections and schedules only; their children inherit them.
    return _date(element.get(f"{LIMS}lastAmendedDate") or element.get(f"{LIMS}inforce-start-date"))


def _date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _text(element: etree._Element) -> str:
    """Element text: inline content on one line, block content one line per child."""
    if not isinstance(element.tag, str):
        return ""
    if element.tag == "row":
        return " | ".join(_text(entry) for entry in element)
    mixed = bool((element.text or "").strip()) or any((c.tail or "").strip() for c in element)
    if mixed or len(element) == 0 or element.tag in ALWAYS_INLINE:
        return " ".join("".join(element.itertext()).split())
    return "\n".join(filter(None, (_text(child) for child in element)))


def _check_unique(segments: list[ParsedSegment]) -> None:
    seen: set[str] = set()
    duplicates = sorted({s.ref for s in segments if s.ref in seen or seen.add(s.ref)})
    if duplicates:
        raise ValueError(f"duplicate refs: {', '.join(duplicates[:10])}")
