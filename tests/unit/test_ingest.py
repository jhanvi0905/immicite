from dataclasses import replace
from datetime import date

import pytest

from app.domain.corpus import Authority, ParsedDocument, ParsedSegment, Source, SourceKind
from app.domain.ports import IngestAlreadyRunning
from app.integrations.fakes import FakeEmbedder, FakeSourceReader, InMemoryCorpusRepository
from app.services.ingest import Outcome, embed_missing, ingest, retire_removed


def source(slug: str = "regs") -> Source:
    return Source(
        slug=slug,
        title="Regulations",
        authority=Authority.REGULATIONS,
        kind=SourceKind.LAW_XML,
        url=f"https://example.test/{slug}.xml",
        licence="test",
        ref_prefix="R",
        web_url=f"https://example.test/{slug}/",
    )


URL = "https://example.test/regs/section-1.html"
SECTION = ParsedSegment("R1", None, "section", 0, ("Part 1",), "", URL, date(2020, 1, 1))
FIRST = ParsedSegment(
    "R1(1)", "R1", "subsection", 1, ("Part 1",), "First rule.", URL, date(2020, 1, 1)
)
SECOND = ParsedSegment(
    "R1(2)", "R1", "subsection", 1, ("Part 1",), "Second rule.", URL, date(2020, 1, 1)
)
DOCUMENT = ParsedDocument((SECTION, FIRST, SECOND), date(2020, 1, 1))


@pytest.fixture
def repository():
    return InMemoryCorpusRepository()


def versions(repository, slug="regs"):
    return next(r for r in repository.rows.values() if r.source.slug == slug).versions


async def test_first_ingest_creates_a_version(repository):
    results = await ingest([source()], FakeSourceReader({"regs": DOCUMENT}), repository)

    assert [(r.outcome, r.segments) for r in results] == [(Outcome.CREATED, 3)]
    assert [s.ref for s in versions(repository)[0].segments] == ["R1", "R1(1)", "R1(2)"]


async def test_ingest_is_idempotent(repository):
    reader = FakeSourceReader({"regs": DOCUMENT})
    await ingest([source()], reader, repository)

    results = await ingest([source()], reader, repository)

    assert results[0].outcome is Outcome.UNCHANGED
    assert len(versions(repository)) == 1
    assert (await repository.status())[0].last_checked_at is not None


async def test_changed_content_appends_a_version(repository):
    reader = FakeSourceReader({"regs": DOCUMENT})
    await ingest([source()], reader, repository)
    reader.documents["regs"] = replace(
        DOCUMENT, segments=(SECTION, FIRST, replace(SECOND, body="Second rule, amended."))
    )

    results = await ingest([source()], reader, repository)

    assert results[0].outcome is Outcome.CREATED
    assert len(versions(repository)) == 2
    assert versions(repository)[0].segments[2].body == "Second rule."
    assert versions(repository)[1].segments[2].body == "Second rule, amended."


async def test_only_changed_segments_are_embedded_again(repository):
    reader, embedder = FakeSourceReader({"regs": DOCUMENT}), FakeEmbedder()
    await ingest([source()], reader, repository, embedder)
    # The section has no text of its own, so there is nothing to embed for it.
    assert embedder.embedded == ["Part 1\nFirst rule.", "Part 1\nSecond rule."]

    embedder.embedded.clear()
    reader.documents["regs"] = replace(
        DOCUMENT, segments=(SECTION, FIRST, replace(SECOND, body="Second rule, amended."))
    )
    await ingest([source()], reader, repository, embedder)

    assert embedder.embedded == ["Part 1\nSecond rule, amended."]
    current = {s.ref: s for s in versions(repository)[-1].segments}
    assert current["R1(1)"].embedding == FakeEmbedder.vector("Part 1\nFirst rule.")
    assert current["R1(2)"].embedding == FakeEmbedder.vector("Part 1\nSecond rule, amended.")


async def test_ingest_without_an_embedder_can_be_backfilled(repository):
    await ingest([source()], FakeSourceReader({"regs": DOCUMENT}), repository)
    assert (await repository.status())[0].unembedded_segments == 2

    embedded = await embed_missing(repository, FakeEmbedder())

    assert embedded == 2
    assert (await repository.status())[0].unembedded_segments == 0


async def test_a_failing_source_does_not_stop_the_others(repository):
    reader = FakeSourceReader({"regs": DOCUMENT})  # nothing registered for "missing"

    results = await ingest([source("missing"), source()], reader, repository)

    assert [r.outcome for r in results] == [Outcome.FAILED, Outcome.CREATED]
    assert "no document for missing" in results[0].error


async def test_an_empty_parse_never_replaces_the_corpus(repository):
    reader = FakeSourceReader({"regs": DOCUMENT})
    await ingest([source()], reader, repository)
    reader.documents["regs"] = ParsedDocument(())

    results = await ingest([source()], reader, repository)

    assert results[0].outcome is Outcome.FAILED
    assert len(versions(repository)) == 1


async def test_dry_run_writes_nothing(repository):
    results = await ingest(
        [source()], FakeSourceReader({"regs": DOCUMENT}), repository, dry_run=True
    )

    assert [(r.outcome, r.segments) for r in results] == [(Outcome.DRY_RUN, 3)]
    assert repository.rows == {}


async def test_only_one_ingest_runs_at_a_time(repository):
    async with repository.ingest_lock():
        with pytest.raises(IngestAlreadyRunning):
            await ingest([source()], FakeSourceReader({"regs": DOCUMENT}), repository)


async def test_a_source_removed_from_the_manifest_is_retired_but_keeps_its_history(repository):
    reader = FakeSourceReader({"regs": DOCUMENT, "other": DOCUMENT})
    await ingest([source(), source("other")], reader, repository)

    retired = await retire_removed([source()], repository)

    assert retired == ["other"]
    status = {s.slug: s for s in await repository.status()}
    assert (status["other"].current_segments, status["other"].versions) == (0, 1)
    assert status["regs"].current_segments == 3
    assert await retire_removed([source()], repository) == []


async def test_a_retired_source_comes_back_when_it_returns_to_the_manifest(repository):
    reader = FakeSourceReader({"regs": DOCUMENT})
    await ingest([source()], reader, repository)
    await retire_removed([], repository)

    results = await ingest([source()], reader, repository)

    assert results[0].outcome is Outcome.CREATED
    assert (await repository.status())[0].current_segments == 3
