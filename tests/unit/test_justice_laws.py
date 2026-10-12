from datetime import date

import pytest

from app.domain.corpus import Authority, LinkOrigin, Source, SourceKind, TargetClass
from app.domain.links import LinkResolver
from app.integrations.sources import justice_laws

# A synthetic regulation in the Justice Laws structure. The text is invented.
REGULATION = b"""<?xml version="1.0"?>
<Regulation xmlns:lims="http://justice.gc.ca/lims" lims:lastAmendedDate="2024-05-01"
            lims:current-date="2024-06-30">
  <Identification><LongTitle>Widget Regulations</LongTitle></Identification>
  <Body>
    <Heading level="1"><Label>PART 1</Label><TitleText>Interpretation</TitleText></Heading>
    <Section lims:inforce-start-date="2010-01-01" lims:lastAmendedDate="2015-03-02">
      <MarginalNote>Definitions</MarginalNote><Label>1</Label>
      <Text>The following definitions apply in these Regulations.</Text>
      <Definition>
        <Text><DefinedTermEn>large widget</DefinedTermEn> means a widget that
          <DefinitionRef>exceeds</DefinitionRef> the limit. (<DefinedTermFr>grand gadget</DefinedTermFr>)</Text>
        <Paragraph><Label>(a)</Label><Text>in height; or</Text></Paragraph>
        <Paragraph><Label>(b)</Label><Text>in width.</Text></Paragraph>
      </Definition>
      <HistoricalNote>SOR/2015-1, s. 1</HistoricalNote>
    </Section>
    <Heading level="1"><Label>PART 2</Label><TitleText>Permits</TitleText></Heading>
    <Heading level="2"><Label>DIVISION 1</Label><TitleText>Issuance</TitleText></Heading>
    <Section lims:inforce-start-date="2012-06-01">
      <MarginalNote>Widget permits</MarginalNote><Label>2</Label>
      <Subsection>
        <MarginalNote>Conditions</MarginalNote><Label>(1)</Label>
        <Text>A permit may be issued under section <XRefInternal>3</XRefInternal> if the applicant</Text>
        <Paragraph><Label>(a)</Label><Text>holds a licence;</Text></Paragraph>
        <Paragraph lims:id="501"><Label>(b)</Label><Text>meets one of the following:</Text>
          <Subparagraph lims:id="502"><Label>(i)</Label><Text>is a resident, or</Text></Subparagraph>
          <Subparagraph><Label>(i.1)</Label><Text>is a visitor</Text>
            <Clause><Label>(A)</Label><Text>with a sponsor.</Text></Clause>
          </Subparagraph>
        </Paragraph>
      </Subsection>
      <Subsection lims:id="510"><Label>(2)</Label><Text>Subsection (1) does not apply to toys
        referred to in paragraph <XRefInternal>1</XRefInternal>(a)(ii) of these Regulations, the
        <XRefExternal reference-type="act" link="W-1">Widget Act</XRefExternal>, the
        <XRefExternal reference-type="act" link="C-46">Criminal Code</XRefExternal> or the
        <XRefExternal reference-type="other">Widget Classification</XRefExternal>.</Text></Subsection>
    </Section>
    <Heading level="2"><Label>DIVISION 2</Label><TitleText>Renewal</TitleText></Heading>
    <Section lims:inforce-start-date="2019-09-09">
      <Label>3</Label><Text><Repealed>[Repealed, SOR/2019-9, s. 4]</Repealed></Text>
    </Section>
  </Body>
  <Schedule lims:inforce-start-date="2011-11-11">
    <ScheduleFormHeading><Label>SCHEDULE 1</Label><TitleText>Fees</TitleText></ScheduleFormHeading>
    <TableGroup><table><tgroup><tbody>
      <row><entry>Permit</entry><entry>$10</entry></row>
      <row><entry>Renewal</entry><entry>$5</entry></row>
    </tbody></tgroup></table></TableGroup>
  </Schedule>
  <Schedule>
    <ScheduleFormHeading type="amending"><TitleText>AMENDMENTS NOT IN FORCE</TitleText></ScheduleFormHeading>
    <BillPiece><Section><Label>2</Label><Text>Not yet law.</Text></Section></BillPiece>
  </Schedule>
  <RecentAmendments><Amendment><Section><Label>2</Label></Section></Amendment></RecentAmendments>
</Regulation>
"""

SOURCE = Source(
    slug="widget-regs",
    title="Widget Regulations",
    authority=Authority.REGULATIONS,
    kind=SourceKind.LAW_XML,
    url="https://example.test/widget.xml",
    licence="test",
    ref_prefix="R",
    web_url="https://example.test/widget-regs/",
)


ACT = SOURCE.model_copy(
    update={
        "slug": "widget-act",
        "ref_prefix": "A",
        "web_url": "https://example.test/eng/acts/W-1/",
    }
)
RESOLVER = LinkResolver(
    {"https://example.test/widget-regs/": "R", "https://laws-lois.justice.gc.ca/eng/acts/w-1/": "A"}
)


def parse(source, raw):
    return justice_laws.parse(source, raw, RESOLVER)


@pytest.fixture(scope="module")
def segments():
    return {s.ref: s for s in parse(SOURCE, REGULATION).segments}


def test_every_addressable_provision_becomes_a_segment_in_document_order():
    refs = [s.ref for s in parse(SOURCE, REGULATION).segments]
    assert refs == [
        "R1",
        "R1#large-widget",
        "R1#large-widget(a)",
        "R1#large-widget(b)",
        "R2",
        "R2(1)",
        "R2(1)(a)",
        "R2(1)(b)",
        "R2(1)(b)(i)",
        "R2(1)(b)(i.1)",
        "R2(1)(b)(i.1)(A)",
        "R2(2)",
        "R3",
        "RSch1",
    ]


def test_segments_form_a_tree(segments):
    clause = segments["R2(1)(b)(i.1)(A)"]
    assert (clause.kind, clause.depth, clause.parent_ref) == ("clause", 4, "R2(1)(b)(i.1)")
    assert (segments["R2"].kind, segments["R2"].depth, segments["R2"].parent_ref) == (
        "section",
        0,
        None,
    )
    assert segments["R1#large-widget(a)"].parent_ref == "R1#large-widget"


def test_body_is_the_provisions_own_text_with_inline_markup_flattened(segments):
    assert segments["R2(1)"].body == "A permit may be issued under section 3 if the applicant"
    assert segments["R2(1)(b)"].body == "meets one of the following:"
    # A section made only of subsections has no text of its own.
    assert segments["R2"].body == ""
    assert segments["R1#large-widget"].body == (
        "large widget means a widget that exceeds the limit. (grand gadget)"
    )


def test_historical_notes_are_not_part_of_the_body(segments):
    assert "SOR/2015-1" not in segments["R1"].body


def test_heading_path_carries_parts_divisions_and_marginal_notes(segments):
    assert segments["R1"].heading_path == ("PART 1 — Interpretation", "Definitions")
    assert segments["R2(1)(a)"].heading_path == (
        "PART 2 — Permits",
        "DIVISION 1 — Issuance",
        "Widget permits",
        "Conditions",
    )
    # A new division replaces the previous one at the same level.
    assert segments["R3"].heading_path == ("PART 2 — Permits", "DIVISION 2 — Renewal")
    assert segments["R1#large-widget"].heading_path[-1] == "large widget"


def test_children_inherit_the_sections_amendment_date(segments):
    assert segments["R1#large-widget(a)"].last_amended_on == date(2015, 3, 2)
    # Without an amendment date, the in-force date is used.
    assert segments["R2(1)(b)(i)"].last_amended_on == date(2012, 6, 1)


def test_repealed_sections_stay_addressable(segments):
    assert segments["R3"].body == "[Repealed, SOR/2019-9, s. 4]"


def test_numbered_schedules_are_one_segment_and_amending_material_is_excluded(segments):
    schedule = segments["RSch1"]
    assert schedule.kind == "schedule"
    assert schedule.heading_path == ("SCHEDULE 1 — Fees",)
    assert schedule.body == "Permit | $10\nRenewal | $5"
    assert schedule.last_amended_on == date(2011, 11, 11)
    assert not any("Not yet law" in s.body for s in segments.values())


def test_urls_point_at_the_section_page_and_anchor_each_provision(segments):
    base = "https://example.test/widget-regs/"
    assert segments["R2"].url == base + "section-2.html"
    assert segments["R2(1)(b)"].url == base + "section-2.html#501"
    assert segments["R2(1)(b)(i)"].url == base + "section-2.html#502"
    # A provision without an id links to its section.
    assert segments["R2(1)(a)"].url == base + "section-2.html"
    # Schedules link to the law itself.
    assert segments["RSch1"].url == base


def test_each_provision_keeps_the_publishers_anchor(segments):
    assert segments["R2(1)(b)"].anchor == "501"
    assert segments["R2(1)(a)"].anchor is None


def test_tagged_cross_references_become_links(segments):
    links = segments["R2(2)"].links
    assert [
        (link.origin, link.target_class, link.target_ref, link.target_url) for link in links
    ] == [
        # A section number, made specific by the labels that follow it.
        (
            LinkOrigin.XML_XREF,
            TargetClass.LAW,
            "R1(a)(ii)",
            "https://example.test/widget-regs/section-1.html",
        ),
        # A law in the corpus, and one that is not.
        (
            LinkOrigin.XML_XREF,
            TargetClass.LAW,
            None,
            "https://laws-lois.justice.gc.ca/eng/acts/w-1/",
        ),
        (
            LinkOrigin.XML_XREF,
            TargetClass.OTHER_LAW,
            None,
            "https://laws-lois.justice.gc.ca/eng/acts/c-46/",
        ),
        # The untagged "Widget Classification" has no address, so there is nothing to record.
    ]
    assert [link.text for link in links] == ["1(a)(ii)", "Widget Act", "Criminal Code"]
    assert [link.target_ref for link in segments["R2(1)"].links] == ["R3"]
    assert segments["R2(1)(a)"].links == ()


def test_published_on_is_the_last_amendment_not_the_consolidation_date():
    assert parse(SOURCE, REGULATION).published_on == date(2024, 5, 1)


def test_duplicate_refs_fail_loudly():
    duplicated = REGULATION.replace(b"<Label>3</Label>", b"<Label>2</Label>")
    with pytest.raises(ValueError, match="duplicate refs: R2"):
        parse(SOURCE, duplicated)


def test_a_section_without_a_label_fails_loudly():
    with pytest.raises(ValueError, match="section without a label"):
        parse(SOURCE, REGULATION.replace(b"<Label>3</Label>", b""))
