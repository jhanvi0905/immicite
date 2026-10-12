"""Ref construction. The formats are part of the public contract (docs/architecture.md).

- Law:         R205(c)(ii), A40(1)        prefix + section label + nested labels
- Definition:  R1(1)#common-law-partner   parent ref + "#" + term slug
- Schedule:    RSch1.1, ASch              prefix + "Sch" + schedule number
- Page:        <source-slug>#<heading-slug>[/<subheading-slug>]

A page's source slug is derived from its address (`page_slug`), so a link to a page names
that page's refs before the page is in the corpus.
"""

import re
import unicodedata
from urllib.parse import urlsplit

PAGE_INTRO_SLUG = "intro"


def slugify(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")


def law_ref(parent_ref: str, label: str) -> str:
    """Append a label to its parent: ("R205", "(c)") -> "R205(c)"; ("R", "205") -> "R205"."""
    return parent_ref + re.sub(r"\s+", "", label)


def definition_ref(parent_ref: str, term: str) -> str:
    return f"{parent_ref}#{slugify(term)}"


def schedule_ref(prefix: str, label: str) -> str:
    """("R", "SCHEDULE 1.1") -> "RSch1.1"; ("A", "SCHEDULE") -> "ASch"."""
    number = re.sub(r"(?i)^schedule", "", label.strip())
    return f"{prefix}Sch{re.sub(r'[^0-9A-Za-z.]+', '', number)}"


def page_ref(source_slug: str, heading_slugs: tuple[str, ...]) -> str:
    return f"{source_slug}#{'/'.join(heading_slugs)}"


CANADA_HOST = "canada.ca"
JUSTICE_HOST = "laws-lois.justice.gc.ca"
JUSTICE_HOST_ALIASES = {"laws.justice.gc.ca", "lois-laws.justice.gc.ca", "lois.justice.gc.ca"}
IRCC_ROOT = "/en/immigration-refugees-citizenship"
OFFICER_INSTRUCTIONS_ROOT = (
    f"{IRCC_ROOT}/corporate/publications-manuals/operational-bulletins-manuals"
)
# Longest first. The slug is the prefix plus the rest of the path.
PAGE_SLUG_PREFIXES = ((OFFICER_INSTRUCTIONS_ROOT, "pdi"), (IRCC_ROOT, "ircc"), ("/en", "canada"))


def normalize_url(url: str) -> tuple[str, str | None]:
    """One spelling per address, and its fragment: https, no www, one Justice Laws host.

    Justice Laws paths are case-insensitive and are lowercased; Canada.ca paths are not.
    """
    parts = urlsplit(url.strip())
    host = parts.netloc.lower().removeprefix("www.")
    if host in JUSTICE_HOST_ALIASES:
        host = JUSTICE_HOST
    path = parts.path.lower() if host == JUSTICE_HOST else parts.path
    query = f"?{parts.query}" if parts.query else ""
    return f"https://{host}{path}{query}", parts.fragment or None


def page_slug(url: str) -> str:
    """The slug of a Canada.ca page, derived from its address alone.

    .../operational-bulletins-manuals/temporary-residents/study-permits/assessing-conditions.html
    -> pdi-temporary-residents-study-permits-assessing-conditions
    """
    parts = urlsplit(normalize_url(url)[0])
    if parts.netloc != CANADA_HOST:
        raise ValueError(f"not a Canada.ca page: {url}")
    path = parts.path.removesuffix(".html").rstrip("/")
    for root, prefix in PAGE_SLUG_PREFIXES:
        if path == root or path.startswith(root + "/"):
            rest = [slugify(part) for part in path[len(root) :].split("/") if part]
            return "-".join([prefix, *rest])
    raise ValueError(f"no slug rule for {url}")
