import logging
from datetime import date

import pytest

from app.domain.corpus import Authority, LinkOrigin, Source, SourceKind, TargetClass
from app.domain.links import LinkResolver
from app.integrations.sources import canada_ca

# A synthetic page in the Canada.ca layout. The text is invented.
PAGE = b"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"/>
<meta name="dcterms.title" content="Widget permit: Who can apply"/>
<meta name="dcterms.modified" title="W3CDTF" content="2026-01-26"/>
</head><body>
<header><h2>Language selection</h2></header>
<main property="mainContentOfPage" class="container">
  <div>
    <nav class="gc-subway"><h1 id="gc-document-nav">Widget permit</h1><ul><li>Apply</li></ul></nav>
    <h1 property="name" id="wb-cont">Who can apply</h1>
  </div>
  <p>Most widget owners need a permit.</p>
  <div><h2>On this page</h2><ul><li><a href="#s1">Requirements</a></li></ul></div>
  <div>
    <h2 id="s1">Requirements</h2>
    <p>You can apply if you</p>
    <ul>
      <li>own a <a href="/widgets.html">widget</a></li>
      <li>can pay for
        <ul><li>the fee</li><li>the inspection <strong>and</strong> the tag</li></ul>
      </li>
    </ul>
    <h3>Fees</h3>
    <table><tr><th>Type</th><th>Fee</th></tr><tr><td>Permit</td><td>$10</td></tr></table>
    <h4>Refunds</h4>
    <p>Fees are not refunded.</p>
    <h3 id="reduced">Fees</h3>
    <details><summary>Reduced fees</summary><p>Caf&eacute; owners pay half.</p></details>
  </div>
  <h2>Exemptions</h2>
  <h3>Toys</h3>
  <p>Toys need no permit under
    <a href="https://laws-lois.justice.gc.ca/eng/regulations/SOR-2002-227/section-205.html">subparagraph 205(c)(ii)</a>;
    see <a href="#s1">requirements</a>,
    the <a href="/en/immigration-refugees-citizenship/corporate/publications-manuals/operational-bulletins-manuals/temporary-residents/study-permits/assessing-conditions.html#leave">instructions</a>,
    <a href="https://www.education.gouv.qc.ca/en/">Quebec</a>
    or <a href="mailto:widgets@example.test">email us</a>.</p>
  <h2>Empty heading</h2>
  <div class="mwspagination"><nav><h2 class="wb-inv">Document navigation</h2></nav></div>
  <section class="pagedetails">
    <h2 class="wb-inv">Page details</h2>
    <div data-ajax-replace="/feedback.html"></div>
    <p>Date modified: 2026-01-26</p>
  </section>
</main>
<footer><h2>About this site</h2></footer>
</body></html>
"""

PAGE_URL = "https://www.canada.ca/en/immigration-refugees-citizenship/services/widget-permit.html"
PDI = "/en/immigration-refugees-citizenship/corporate/publications-manuals/operational-bulletins-manuals"
SOURCE = Source(
    title="Widget permit",
    authority=Authority.PUBLIC_GUIDANCE,
    kind=SourceKind.WEB_PAGE,
    url=PAGE_URL,
    licence="test",
)
RESOLVER = LinkResolver({"https://laws-lois.justice.gc.ca/eng/regulations/sor-2002-227/": "R"})


def parse(source, raw):
    return canada_ca.parse(source, raw, RESOLVER)


@pytest.fixture(scope="module")
def segments():
    return {s.ref: s for s in parse(SOURCE, PAGE).segments}


def test_the_page_is_cut_at_h2_and_h3_in_document_order():
    assert [(s.ref, s.kind, s.depth) for s in parse(SOURCE, PAGE).segments] == [
        ("ircc-services-widget-permit#intro", "intro", 0),
        ("ircc-services-widget-permit#requirements", "section", 0),
        ("ircc-services-widget-permit#requirements/fees", "subsection", 1),
        ("ircc-services-widget-permit#requirements/fees-2", "subsection", 1),
        ("ircc-services-widget-permit#exemptions", "section", 0),
        ("ircc-services-widget-permit#exemptions/toys", "subsection", 1),
    ]


def test_subsections_point_to_their_section(segments):
    assert (
        segments["ircc-services-widget-permit#requirements/fees"].parent_ref
        == "ircc-services-widget-permit#requirements"
    )
    assert segments["ircc-services-widget-permit#requirements"].parent_ref is None


def test_heading_path_starts_with_the_page_title(segments):
    assert segments["ircc-services-widget-permit#intro"].heading_path == ("Who can apply",)
    assert segments["ircc-services-widget-permit#exemptions/toys"].heading_path == (
        "Who can apply",
        "Exemptions",
        "Toys",
    )


def test_lists_become_indented_bullets_and_links_become_text(segments):
    assert segments["ircc-services-widget-permit#requirements"].body == (
        "You can apply if you\n"
        "- own a widget\n"
        "- can pay for\n"
        "  - the fee\n"
        "  - the inspection and the tag"
    )


def test_tables_and_lower_headings_stay_in_the_body(segments):
    assert segments["ircc-services-widget-permit#requirements/fees"].body == (
        "Type | Fee\nPermit | $10\nRefunds\nFees are not refunded."
    )
    assert segments["ircc-services-widget-permit#requirements/fees-2"].body == (
        "Reduced fees\nCafé owners pay half."
    )


def test_page_furniture_is_left_out(segments):
    text = " ".join(s.body for s in segments.values())
    for furniture in ("Language selection", "Apply", "On this page", "Date modified", "About this"):
        assert furniture not in text
    assert segments["ircc-services-widget-permit#intro"].body == "Most widget owners need a permit."


def test_a_section_with_only_subsections_is_kept_and_an_empty_one_is_dropped(segments):
    assert segments["ircc-services-widget-permit#exemptions"].body == ""
    assert "ircc-services-widget-permit#empty-heading" not in segments


def test_every_segment_is_dated_from_the_page(segments):
    assert parse(SOURCE, PAGE).published_on == date(2026, 1, 26)
    assert {s.last_amended_on for s in segments.values()} == {date(2026, 1, 26)}


def test_urls_use_the_heading_anchor_when_there_is_one(segments):
    page = PAGE_URL
    assert segments["ircc-services-widget-permit#requirements"].url == page + "#s1"
    assert segments["ircc-services-widget-permit#requirements/fees-2"].url == page + "#reduced"
    # No id on the heading, and the intro: link to the page.
    assert segments["ircc-services-widget-permit#exemptions"].url == page
    assert segments["ircc-services-widget-permit#intro"].url == page


def test_the_heading_anchor_is_kept_for_incoming_links(segments):
    assert segments["ircc-services-widget-permit#requirements"].anchor == "s1"
    assert segments["ircc-services-widget-permit#exemptions"].anchor is None


def test_body_links_are_recorded_on_the_section_they_appear_in(segments):
    links = segments["ircc-services-widget-permit#exemptions/toys"].links
    assert [(link.target_class, link.target_ref, link.target_fragment) for link in links] == [
        # The address names the section; the link's words name the clause.
        (TargetClass.LAW, "R205(c)(ii)", None),
        (TargetClass.SAME_PAGE, "ircc-services-widget-permit", "s1"),
        # A page we do not hold still gets the slug it would have.
        (
            TargetClass.OFFICER_INSTRUCTIONS,
            "pdi-temporary-residents-study-permits-assessing-conditions",
            "leave",
        ),
        (TargetClass.EXTERNAL, None, None),
        # mailto: is not a web address, so it is not a link.
    ]
    assert {link.origin for link in links} == {LinkOrigin.HTML_LINK}
    assert links[0].text == "subparagraph 205(c)(ii)"
    assert links[0].target_url == (
        "https://laws-lois.justice.gc.ca/eng/regulations/sor-2002-227/section-205.html"
    )
    assert links[2].target_url == "https://canada.ca" + PDI + (
        "/temporary-residents/study-permits/assessing-conditions.html"
    )


def test_the_table_of_contents_and_menus_contribute_no_links(segments):
    targets = [link.target_url for s in segments.values() for link in s.links]
    # Only the "widget" body link and the five links above; the "On this page" entry is skipped.
    assert len(targets) == 5
    assert segments["ircc-services-widget-permit#requirements"].links[0].target_class == (
        TargetClass.GOVERNMENT
    )


def test_a_page_without_main_fails_loudly():
    with pytest.raises(ValueError, match="no <main>"):
        parse(SOURCE, b"<html><body><p>Access denied</p></body></html>")


def test_content_loaded_by_script_is_reported(caplog):
    page = PAGE.replace(b"<h2>Exemptions</h2>", b'<div data-ajax-replace="/x.html"></div>')
    with caplog.at_level(logging.WARNING):
        parse(SOURCE, page)
    assert "loaded by script" in caplog.text
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        parse(SOURCE, PAGE)
    assert caplog.text == ""
