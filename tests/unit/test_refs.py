import pytest

from app.domain.refs import (
    definition_ref,
    law_ref,
    normalize_url,
    page_ref,
    page_slug,
    schedule_ref,
    slugify,
)


def test_law_ref_appends_labels_to_the_parent():
    assert law_ref("R", "205") == "R205"
    assert law_ref(law_ref("R205", "(c)"), "(ii)") == "R205(c)(ii)"
    assert law_ref("A", "40.1") == "A40.1"


def test_definition_ref_uses_the_term_slug():
    assert definition_ref("R1(1)", "common-law partner") == "R1(1)#common-law-partner"
    assert definition_ref("A2(1)", "foreign national") == "A2(1)#foreign-national"


def test_schedule_ref_keeps_the_schedule_number():
    assert schedule_ref("R", "SCHEDULE 1.1") == "RSch1.1"
    assert schedule_ref("A", "SCHEDULE") == "ASch"


def test_page_ref_nests_subheadings():
    assert page_ref("study-permit", ("eligibility",)) == "study-permit#eligibility"
    assert page_ref("study-permit", ("eligibility", "funds")) == "study-permit#eligibility/funds"


def test_slugify_drops_accents_and_punctuation():
    assert slugify("  Who can apply?  ") == "who-can-apply"
    assert slugify("Études au Québec") == "etudes-au-quebec"


def test_normalize_url_gives_one_spelling_per_address():
    assert normalize_url("http://www.canada.ca/en/Page.html#s12") == (
        "https://canada.ca/en/Page.html",
        "s12",
    )
    # Justice Laws paths are case-insensitive, and the site answers on several hosts.
    assert normalize_url(
        "https://laws.justice.gc.ca/eng/regulations/SOR-2002-227/section-205.html"
    ) == (
        "https://laws-lois.justice.gc.ca/eng/regulations/sor-2002-227/section-205.html",
        None,
    )


def test_page_slug_is_derived_from_the_address():
    root = "https://www.canada.ca/en/immigration-refugees-citizenship"
    manuals = f"{root}/corporate/publications-manuals/operational-bulletins-manuals"
    assert page_slug(f"{manuals}/temporary-residents/study-permits/assessing-conditions.html") == (
        "pdi-temporary-residents-study-permits-assessing-conditions"
    )
    assert page_slug(f"{manuals}.html") == "pdi"
    assert (
        page_slug(f"{root}/services/study-canada/work.html#s1") == "ircc-services-study-canada-work"
    )
    assert page_slug("https://canada.ca/en/services/immigration-citizenship.html") == (
        "canada-services-immigration-citizenship"
    )


def test_page_slug_rejects_addresses_it_has_no_rule_for():
    with pytest.raises(ValueError, match="not a Canada.ca page"):
        page_slug("https://example.test/en/page.html")
    with pytest.raises(ValueError, match="no slug rule"):
        page_slug("https://www.canada.ca/fr/page.html")
