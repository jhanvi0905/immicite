"""The corpus as the domain sees it: sources, and the segments parsed from them."""

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator

from app.domain.refs import page_slug


class Authority(StrEnum):
    """Level of legal authority, highest first.

    Rank orders the levels; it does not by itself settle every conflict. A ministerial
    instruction or public policy can lawfully depart from the Regulations, so a conflict
    involving that level is shown, not resolved by rank (ADR 0011).
    """

    ACT = "act"
    REGULATIONS = "regulations"
    MINISTERIAL_INSTRUCTIONS = "ministerial_instructions"  # and public policies
    OFFICER_INSTRUCTIONS = "officer_instructions"
    PUBLIC_GUIDANCE = "public_guidance"

    @property
    def rank(self) -> int:
        """1 is the highest authority."""
        return list(Authority).index(self) + 1


class SourceKind(StrEnum):
    """The format a source is published in, which decides how it is parsed."""

    LAW_XML = "law_xml"
    WEB_PAGE = "web_page"


class Source(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    slug: str
    title: str
    authority: Authority
    kind: SourceKind
    url: str
    licence: str
    programs: tuple[str, ...] = ()
    language: str = "en"
    # Law only: the letter refs start with, "A" for the Act and "R" for the Regulations.
    ref_prefix: str | None = None
    # Law only: where the law is published for reading. Citation links are built from it.
    web_url: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _page_slug_comes_from_its_url(cls, data: dict) -> dict:
        # A page's slug is derived, never chosen, so that a link to a page that is not in
        # the corpus yet already names the ref the page will get (domain/refs.py).
        if isinstance(data, dict) and data.get("kind") == SourceKind.WEB_PAGE:
            derived = page_slug(data["url"])
            if data.get("slug", derived) != derived:
                raise ValueError(f"{data['slug']}: a page's slug is derived from its url")
            data = {**data, "slug": derived}
        return data

    @model_validator(mode="after")
    def _law_needs_ref_prefix_and_web_url(self) -> "Source":
        if self.kind is SourceKind.LAW_XML and not (self.ref_prefix and self.web_url):
            raise ValueError(f"{self.slug}: a law source needs ref_prefix and web_url")
        return self


class LinkOrigin(StrEnum):
    HTML_LINK = "html_link"  # a hyperlink in a page's body
    XML_XREF = "xml_xref"  # a cross-reference tag in the law XML
    TEXT_MENTION = "text_mention"  # a ref written in plain text (not extracted yet)


class TargetClass(StrEnum):
    """What kind of thing a link points at, as far as its address alone can tell."""

    SAME_PAGE = "same_page"
    LAW = "law"  # a law in the corpus
    OTHER_LAW = "other_law"  # any other federal act or regulation
    OFFICER_INSTRUCTIONS = "officer_instructions"
    IRCC_PAGE = "ircc_page"
    GAZETTE = "gazette"
    GOVERNMENT = "government"  # another federal page
    EXTERNAL = "external"


@dataclass(frozen=True)
class ParsedLink:
    """A link from a segment. `target_ref` names the target whether or not we hold it:
    a law ref (`R205(c)(ii)`), or a page's slug, with `target_fragment` naming the section.
    """

    origin: LinkOrigin
    text: str
    target_url: str
    target_fragment: str | None
    target_class: TargetClass
    target_ref: str | None


@dataclass(frozen=True)
class ParsedSegment:
    """One addressable piece of a source: a clause of law or a section of a page.

    `body` is the segment's own text only. Its children carry theirs.
    `url` is the official page for the segment, as close to it as the publisher allows.
    `anchor` is the publisher's own id for the segment, which incoming links use.
    """

    ref: str
    parent_ref: str | None
    kind: str
    depth: int
    heading_path: tuple[str, ...]
    body: str
    url: str
    last_amended_on: date | None = None
    anchor: str | None = None
    links: tuple[ParsedLink, ...] = ()


@dataclass(frozen=True)
class ParsedDocument:
    """A source's segments in document order, parents before their children."""

    segments: tuple[ParsedSegment, ...]
    published_on: date | None = None


@dataclass(frozen=True)
class SourceStatus:
    slug: str
    authority: str
    versions: int
    current_segments: int
    unembedded_segments: int
    published_on: date | None
    last_checked_at: datetime | None


def embedding_text(heading_path: tuple[str, ...], body: str) -> str:
    """The text embedded for a segment: where it sits, then what it says."""
    return "\n".join([" > ".join(heading_path), body]).strip()
