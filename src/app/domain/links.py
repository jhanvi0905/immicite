"""Turns a raw link into a ParsedLink: a normalised address, its class, and the ref it names."""

import re
from collections.abc import Iterable, Mapping
from urllib.parse import urljoin, urlsplit

from app.domain.corpus import LinkOrigin, ParsedLink, Source, SourceKind, TargetClass
from app.domain.refs import (
    CANADA_HOST,
    IRCC_ROOT,
    JUSTICE_HOST,
    OFFICER_INSTRUCTIONS_ROOT,
    normalize_url,
    page_slug,
)

GAZETTE_HOST = "gazette.gc.ca"
JUSTICE_ROOT = f"https://{JUSTICE_HOST}/eng/"
# Labels that follow a section number: "(1)", "(c)(ii)", "(i.1)(A)".
_LABELS = r"((?:\([0-9A-Za-z.]+\))+)"


class LinkResolver:
    """Knows which laws are in the corpus, so a link into one can name its ref."""

    def __init__(self, laws: Mapping[str, str]) -> None:
        # Normalised reading-site address of each law -> its ref prefix.
        self._laws = dict(laws)

    @classmethod
    def from_sources(cls, sources: Iterable[Source]) -> "LinkResolver":
        return cls(
            {
                normalize_url(s.web_url)[0]: s.ref_prefix
                for s in sources
                if s.kind is SourceKind.LAW_XML
            }
        )

    def html_link(self, page_url: str, href: str, text: str) -> ParsedLink | None:
        """A hyperlink found in the body of `page_url`. None when it is not a web address."""
        absolute = urljoin(page_url, href.strip())
        if urlsplit(absolute).scheme not in ("http", "https"):
            return None
        url, fragment = normalize_url(absolute)
        host, path = urlsplit(url).netloc, urlsplit(url).path

        if url == normalize_url(page_url)[0]:
            if not fragment:
                return None
            target_class, ref = TargetClass.SAME_PAGE, page_slug(url)
        elif host == JUSTICE_HOST:
            target_class, ref = self._law(url, text)
        elif host == CANADA_HOST:
            if _under(path, OFFICER_INSTRUCTIONS_ROOT):
                target_class = TargetClass.OFFICER_INSTRUCTIONS
            elif _under(path, IRCC_ROOT):
                target_class = TargetClass.IRCC_PAGE
            else:
                target_class = TargetClass.GOVERNMENT
            ref = page_slug(url) if path.endswith(".html") and _under(path, "/en") else None
        elif host == GAZETTE_HOST:
            target_class, ref = TargetClass.GAZETTE, None
        elif host.endswith((".gc.ca", "." + CANADA_HOST)):
            target_class, ref = TargetClass.GOVERNMENT, None
        else:
            target_class, ref = TargetClass.EXTERNAL, None
        return ParsedLink(LinkOrigin.HTML_LINK, text, url, fragment, target_class, ref)

    def section_xref(self, source: Source, section: str, following_text: str) -> ParsedLink | None:
        """A tagged reference to a section of the same law, e.g. `<XRefInternal>7.01</…>(2)(b)`.

        None when the tag holds anything but a section number.
        """
        if not re.fullmatch(r"[0-9]+(\.[0-9]+)*", section):
            return None
        labels = re.match(_LABELS, following_text)
        url, _ = normalize_url(f"{source.web_url}section-{section}.html")
        return ParsedLink(
            origin=LinkOrigin.XML_XREF,
            text=section + (labels.group(1) if labels else ""),
            target_url=url,
            target_fragment=None,
            target_class=TargetClass.LAW,
            target_ref=source.ref_prefix + section + (labels.group(1) if labels else ""),
        )

    def law_xref(self, kind: str, law_id: str, text: str) -> ParsedLink | None:
        """A tagged reference to another act or regulation as a whole."""
        folder = {"act": "acts", "regulation": "regulations"}.get(kind)
        if folder is None or not law_id:
            return None
        url, _ = normalize_url(f"{JUSTICE_ROOT}{folder}/{law_id}/")
        target_class = TargetClass.LAW if url in self._laws else TargetClass.OTHER_LAW
        return ParsedLink(LinkOrigin.XML_XREF, text, url, None, target_class, None)

    def _law(self, url: str, text: str) -> tuple[TargetClass, str | None]:
        prefix = next((p for base, p in self._laws.items() if url.startswith(base)), None)
        if prefix is None:
            return TargetClass.OTHER_LAW, None
        section = re.search(r"/section-([0-9.]+)\.html$", url)
        if section is None:
            return TargetClass.LAW, None
        number = section.group(1)
        # The address stops at the section. The link's words often name the clause.
        labels = re.search(rf"(?<![\w.]){re.escape(number)}{_LABELS}", text)
        return TargetClass.LAW, prefix + number + (labels.group(1) if labels else "")


def _under(path: str, root: str) -> bool:
    return path == root or path.startswith(root + "/") or path == root + ".html"
