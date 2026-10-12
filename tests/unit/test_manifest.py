from pathlib import Path

import pytest

from app.domain.corpus import Authority, SourceKind
from app.integrations.sources.manifest import load_manifest

ENTRY = """
  - slug: {slug}
    title: Some Act
    authority: act
    kind: law_xml
    {prefix}
    url: https://example.test/act.xml
    licence: test
"""


LAW_FIELDS = "ref_prefix: A\n    web_url: https://example.test/act/"


def write(tmp_path: Path, *entries: str) -> Path:
    path = tmp_path / "sources.yaml"
    path.write_text("sources:" + "".join(entries))
    return path


def test_loads_sources(tmp_path):
    [source] = load_manifest(write(tmp_path, ENTRY.format(slug="act", prefix=LAW_FIELDS)))

    assert (source.slug, source.authority, source.kind) == (
        "act",
        Authority.ACT,
        SourceKind.LAW_XML,
    )
    assert (source.language, source.programs, source.ref_prefix) == ("en", (), "A")


def test_duplicate_slugs_are_rejected(tmp_path):
    entry = ENTRY.format(slug="act", prefix=LAW_FIELDS)
    with pytest.raises(ValueError, match="duplicate source slugs"):
        load_manifest(write(tmp_path, entry, entry))


@pytest.mark.parametrize("fields", ["", "ref_prefix: A", "web_url: https://example.test/act/"])
def test_law_without_a_ref_prefix_and_web_url_is_rejected(tmp_path, fields):
    with pytest.raises(ValueError, match="needs ref_prefix and web_url"):
        load_manifest(write(tmp_path, ENTRY.format(slug="act", prefix=fields)))


PAGE = """
  - title: Some page
    authority: public_guidance
    kind: web_page
    {slug}
    url: https://www.canada.ca/en/immigration-refugees-citizenship/services/study-canada/work.html
    licence: test
"""


def test_a_pages_slug_is_derived_from_its_url(tmp_path):
    [source] = load_manifest(write(tmp_path, PAGE.format(slug="")))

    assert source.slug == "ircc-services-study-canada-work"


def test_a_page_cannot_choose_its_own_slug(tmp_path):
    with pytest.raises(ValueError, match="derived from its url"):
        load_manifest(write(tmp_path, PAGE.format(slug="slug: my-page")))


def test_authority_levels_are_ranked_highest_first():
    assert [level.rank for level in Authority] == [1, 2, 3, 4, 5]
    assert Authority.ACT.rank < Authority.REGULATIONS.rank < Authority.OFFICER_INSTRUCTIONS.rank


def test_the_repository_manifest_is_valid():
    sources = load_manifest(Path(__file__).parents[2] / "sources.yaml")

    assert {"irpa", "irpr"} <= {s.slug for s in sources}
