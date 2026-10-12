from dataclasses import replace
from datetime import date

from app.domain.corpus import LinkOrigin, ParsedDocument, ParsedLink, ParsedSegment, TargetClass
from app.domain.hashing import content_hash, text_hash

URL = "https://example.test/regs/section-1.html"
LINK = ParsedLink(
    LinkOrigin.HTML_LINK,
    "section 2",
    "https://example.test/regs/section-2.html",
    None,
    TargetClass.LAW,
    "R2",
)
SEGMENT = ParsedSegment("R1", None, "section", 0, ("Part 1",), "Some text.", URL, date(2020, 1, 1))
DOCUMENT = ParsedDocument((SEGMENT,), date(2024, 1, 1))


def test_content_hash_is_stable():
    same = ParsedDocument((replace(SEGMENT),), date(2024, 1, 1))
    assert content_hash(DOCUMENT) == content_hash(same)


def test_content_hash_changes_with_text_dates_and_structure():
    variants = [
        ParsedDocument((replace(SEGMENT, body="Other text."),), DOCUMENT.published_on),
        ParsedDocument(
            (replace(SEGMENT, last_amended_on=date(2021, 1, 1)),), DOCUMENT.published_on
        ),
        ParsedDocument((replace(SEGMENT, ref="R2"),), DOCUMENT.published_on),
        ParsedDocument(
            (replace(SEGMENT, url="https://example.test/moved"),), DOCUMENT.published_on
        ),
        ParsedDocument((replace(SEGMENT, anchor="s1"),), DOCUMENT.published_on),
        ParsedDocument((replace(SEGMENT, links=(LINK,)),), DOCUMENT.published_on),
        ParsedDocument((SEGMENT,), date(2025, 1, 1)),
    ]
    hashes = {content_hash(v) for v in variants} | {content_hash(DOCUMENT)}
    assert len(hashes) == len(variants) + 1


def test_text_hash_ignores_what_is_not_embedded():
    assert text_hash(SEGMENT) == text_hash(
        replace(SEGMENT, last_amended_on=None, depth=3, url="https://example.test/moved")
    )
    assert text_hash(SEGMENT) == text_hash(replace(SEGMENT, anchor="s1", links=(LINK,)))
    assert text_hash(SEGMENT) != text_hash(replace(SEGMENT, body="Other text."))
    assert text_hash(SEGMENT) != text_hash(replace(SEGMENT, heading_path=("Part 2",)))
