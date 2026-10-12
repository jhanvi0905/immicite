from dataclasses import replace
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.domain.corpus import (
    Authority,
    LinkOrigin,
    ParsedDocument,
    ParsedLink,
    ParsedSegment,
    Source,
    SourceKind,
    TargetClass,
)
from app.domain.ports import IngestAlreadyRunning
from app.integrations.db.repository import PostgresCorpusRepository, create_engine
from app.integrations.fakes import FakeEmbedder, FakeSourceReader
from app.services.ingest import Outcome, embed_missing, ingest, retire_removed

SOURCE = Source(
    slug="regs",
    title="Regulations",
    authority=Authority.REGULATIONS,
    kind=SourceKind.LAW_XML,
    url="https://example.test/regs.xml",
    licence="test",
    programs=("study-permit",),
    ref_prefix="R",
    web_url="https://example.test/regs/",
)
URL = "https://example.test/regs/section-1.html"
SECTION = ParsedSegment("R1", None, "section", 0, ("Part 1",), "", URL, date(2020, 1, 1))
FIRST = ParsedSegment(
    "R1(1)", "R1", "subsection", 1, ("Part 1",), "Permits expire.", URL, date(2020, 1, 1)
)
SECOND = ParsedSegment(
    "R1(2)", "R1", "subsection", 1, ("Part 1",), "Students may work.", URL, date(2020, 1, 1)
)
DOCUMENT = ParsedDocument((SECTION, FIRST, SECOND), date(2020, 1, 1))
AMENDED = replace(
    DOCUMENT, segments=(SECTION, FIRST, replace(SECOND, body="Students may not work."))
)


async def rows(engine, sql: str, **params):
    async with engine.connect() as conn:
        return (await conn.execute(text(sql), params)).all()


async def test_ingest_stores_a_source_its_version_and_a_segment_tree(engine, repository):
    results = await ingest([SOURCE], FakeSourceReader({"regs": DOCUMENT}), repository)

    assert results[0].outcome is Outcome.CREATED
    assert await rows(engine, "SELECT slug, authority, programs, language FROM sources") == [
        ("regs", "regulations", ["study-permit"], "en")
    ]
    assert await rows(engine, "SELECT raw, published_on FROM source_versions") == [
        (b"regs", date(2020, 1, 1))
    ]
    segments = await rows(
        engine,
        """
        SELECT s.ref, p.ref, s.kind, s.depth, s.position, s.heading_path, s.body,
               s.last_amended_on, s.is_current, s.embedding IS NULL
        FROM segments s LEFT JOIN segments p ON p.id = s.parent_id ORDER BY s.position
        """,
    )
    assert segments == [
        ("R1", None, "section", 0, 0, ["Part 1"], "", date(2020, 1, 1), True, True),
        (
            "R1(1)",
            "R1",
            "subsection",
            1,
            1,
            ["Part 1"],
            "Permits expire.",
            date(2020, 1, 1),
            True,
            True,
        ),
        (
            "R1(2)",
            "R1",
            "subsection",
            1,
            2,
            ["Part 1"],
            "Students may work.",
            date(2020, 1, 1),
            True,
            True,
        ),
    ]


async def test_every_segment_stores_its_url(engine, repository):
    await ingest([SOURCE], FakeSourceReader({"regs": DOCUMENT}), repository)

    assert await rows(engine, "SELECT DISTINCT url FROM segments") == [(URL,)]


async def test_ingest_is_idempotent(engine, repository):
    reader = FakeSourceReader({"regs": DOCUMENT})
    await ingest([SOURCE], reader, repository)

    results = await ingest([SOURCE], reader, repository)

    assert results[0].outcome is Outcome.UNCHANGED
    assert await rows(engine, "SELECT count(*) FROM source_versions") == [(1,)]
    assert await rows(engine, "SELECT count(*) FROM segments") == [(3,)]


async def test_a_new_version_replaces_the_current_segments_and_keeps_the_old_ones(
    engine, repository
):
    reader = FakeSourceReader({"regs": DOCUMENT})
    await ingest([SOURCE], reader, repository)
    reader.documents["regs"] = AMENDED

    await ingest([SOURCE], reader, repository)

    assert await rows(engine, "SELECT count(*) FROM source_versions") == [(2,)]
    assert await rows(
        engine, "SELECT ref, body, is_current FROM segments WHERE ref = 'R1(2)' ORDER BY is_current"
    ) == [("R1(2)", "Students may work.", False), ("R1(2)", "Students may not work.", True)]
    assert await rows(engine, "SELECT count(*) FROM segments WHERE is_current") == [(3,)]


async def test_full_text_search_sees_only_current_segments(engine, repository):
    reader = FakeSourceReader({"regs": DOCUMENT})
    await ingest([SOURCE], reader, repository)
    reader.documents["regs"] = AMENDED
    await ingest([SOURCE], reader, repository)

    found = await rows(
        engine,
        """
        SELECT body FROM segments
        WHERE is_current AND tsv @@ plainto_tsquery('english', 'student working')
        """,
    )

    assert found == [("Students may not work.",)]


async def test_unchanged_segments_keep_their_embedding_across_versions(engine, repository):
    reader, embedder = FakeSourceReader({"regs": DOCUMENT}), FakeEmbedder()
    await ingest([SOURCE], reader, repository, embedder)
    reader.documents["regs"] = AMENDED

    # No embedder this time: unchanged text keeps its vector, changed text waits.
    await ingest([SOURCE], reader, repository)

    current = "SELECT ref, embedding IS NOT NULL FROM segments WHERE is_current ORDER BY position"
    assert await rows(engine, current) == [("R1", False), ("R1(1)", True), ("R1(2)", False)]
    assert (await repository.status())[0].unembedded_segments == 1

    assert await embed_missing(repository, FakeEmbedder()) == 1
    assert await rows(engine, current) == [("R1", False), ("R1(1)", True), ("R1(2)", True)]


async def test_a_failed_version_leaves_the_previous_one_current(engine, repository):
    reader = FakeSourceReader({"regs": DOCUMENT})
    await ingest([SOURCE], reader, repository)
    # A duplicate ref violates a constraint partway through the insert.
    reader.documents["regs"] = replace(DOCUMENT, segments=(SECTION, FIRST, FIRST))

    results = await ingest([SOURCE], reader, repository)

    assert results[0].outcome is Outcome.FAILED
    assert await rows(engine, "SELECT count(*) FROM source_versions") == [(1,)]
    assert await rows(engine, "SELECT ref FROM segments WHERE is_current ORDER BY position") == [
        ("R1",),
        ("R1(1)",),
        ("R1(2)",),
    ]


async def test_two_sources_cannot_hold_the_same_current_ref(engine, repository):
    await ingest([SOURCE], FakeSourceReader({"regs": DOCUMENT}), repository)
    other = SOURCE.model_copy(update={"slug": "other"})

    results = await ingest([other], FakeSourceReader({"other": DOCUMENT}), repository)

    assert results[0].outcome is Outcome.FAILED
    assert await rows(engine, "SELECT count(*) FROM segments") == [(3,)]


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE source_versions SET content_hash = 'x'",
        "DELETE FROM source_versions",
        "TRUNCATE source_versions CASCADE",
    ],
)
async def test_versions_are_append_only(engine, repository, statement):
    await ingest([SOURCE], FakeSourceReader({"regs": DOCUMENT}), repository)

    with pytest.raises((DBAPIError, IntegrityError), match="append-only"):
        async with engine.begin() as conn:
            await conn.execute(text(statement))


async def test_only_one_ingest_runs_at_a_time(database_url, repository):
    other_engine = create_engine(database_url)
    try:
        async with PostgresCorpusRepository(other_engine).ingest_lock():
            with pytest.raises(IngestAlreadyRunning):
                await ingest([SOURCE], FakeSourceReader({"regs": DOCUMENT}), repository)
        # Released on exit, so the next run goes ahead.
        results = await ingest([SOURCE], FakeSourceReader({"regs": DOCUMENT}), repository)
        assert results[0].outcome is Outcome.CREATED
    finally:
        await other_engine.dispose()


async def test_status_reports_each_source(repository):
    await ingest([SOURCE], FakeSourceReader({"regs": DOCUMENT}), repository)

    [status] = await repository.status()

    assert (status.slug, status.authority, status.versions) == ("regs", "regulations", 1)
    assert (status.current_segments, status.unembedded_segments) == (3, 2)
    assert status.published_on == date(2020, 1, 1)
    assert status.last_checked_at is not None


async def test_a_source_removed_from_the_manifest_leaves_the_current_corpus(engine, repository):
    other = SOURCE.model_copy(update={"slug": "other"})
    other_document = ParsedDocument(
        (ParsedSegment("other#intro", None, "intro", 0, ("Other",), "Some guidance.", URL),)
    )
    reader = FakeSourceReader({"regs": DOCUMENT, "other": other_document})
    await ingest([SOURCE, other], reader, repository)

    assert await retire_removed([SOURCE], repository) == ["other"]

    assert await rows(engine, "SELECT ref, is_current FROM segments WHERE ref LIKE 'other%'") == [
        ("other#intro", False)
    ]
    assert await rows(engine, "SELECT count(*) FROM segments WHERE is_current") == [(3,)]
    assert await rows(engine, "SELECT count(*) FROM source_versions") == [(2,)]

    # Back in the manifest with the same content: it becomes current again.
    results = await ingest([SOURCE, other], reader, repository)
    assert [r.outcome for r in results] == [Outcome.UNCHANGED, Outcome.CREATED]
    assert await rows(engine, "SELECT count(*) FROM segments WHERE is_current") == [(4,)]


async def test_links_and_anchors_are_stored_with_their_segment(engine, repository):
    law = ParsedLink(
        LinkOrigin.XML_XREF,
        "44",
        "https://example.test/regs/section-44.html",
        None,
        TargetClass.LAW,
        "R44",
    )
    missing = ParsedLink(
        LinkOrigin.HTML_LINK,
        "the list",
        "https://canada.ca/en/list.html",
        "s2",
        TargetClass.GOVERNMENT,
        "canada-list",
    )
    linked = replace(FIRST, anchor="501", links=(law, missing))
    document = replace(DOCUMENT, segments=(SECTION, linked, SECOND))

    await ingest([SOURCE], FakeSourceReader({"regs": document}), repository)

    assert await rows(engine, "SELECT ref, anchor FROM segments ORDER BY position") == [
        ("R1", None),
        ("R1(1)", "501"),
        ("R1(2)", None),
    ]
    assert await rows(
        engine,
        """
        SELECT s.ref, l.position, l.origin, l.link_text, l.target_url, l.target_fragment,
               l.target_class, l.target_ref
        FROM segment_links l JOIN segments s ON s.id = l.segment_id ORDER BY l.position
        """,
    ) == [
        (
            "R1(1)",
            0,
            "xml_xref",
            "44",
            "https://example.test/regs/section-44.html",
            None,
            "law",
            "R44",
        ),
        (
            "R1(1)",
            1,
            "html_link",
            "the list",
            "https://canada.ca/en/list.html",
            "s2",
            "government",
            "canada-list",
        ),
    ]


async def test_a_changed_link_makes_a_new_version_without_re_embedding(engine, repository):
    link = ParsedLink(
        LinkOrigin.HTML_LINK,
        "the list",
        "https://canada.ca/en/list.html",
        None,
        TargetClass.GOVERNMENT,
        "canada-list",
    )
    reader, embedder = FakeSourceReader({"regs": DOCUMENT}), FakeEmbedder()
    await ingest([SOURCE], reader, repository, embedder)
    embedder.embedded.clear()
    reader.documents["regs"] = replace(
        DOCUMENT, segments=(SECTION, replace(FIRST, links=(link,)), SECOND)
    )

    results = await ingest([SOURCE], reader, repository, embedder)

    assert results[0].outcome is Outcome.CREATED
    assert embedder.embedded == []
    assert await rows(
        engine, "SELECT count(*) FROM segments WHERE is_current AND embedding IS NOT NULL"
    ) == [(2,)]


async def test_sources_are_ordered_by_authority(repository):
    act = SOURCE.model_copy(update={"slug": "act", "authority": Authority.ACT, "ref_prefix": "A"})
    act_document = ParsedDocument((ParsedSegment("A1", None, "section", 0, (), "An act.", URL),))
    reader = FakeSourceReader({"regs": DOCUMENT, "act": act_document})

    await ingest([SOURCE, act], reader, repository)

    assert [s.slug for s in await repository.status()] == ["act", "regs"]


async def test_segments_by_ref_returns_current_segments_in_the_order_asked(repository):
    await ingest([SOURCE], FakeSourceReader({"regs": DOCUMENT}), repository)
    await ingest([SOURCE], FakeSourceReader({"regs": AMENDED}), repository)

    second, first = await repository.segments_by_ref(["R1(2)", "R9", "R1(1)", "R1(2)"])

    assert (second.ref, second.body) == ("R1(2)", "Students may not work.")
    assert (first.ref, first.authority, first.heading_path, first.url, first.last_amended_on) == (
        "R1(1)",
        Authority.REGULATIONS,
        ("Part 1",),
        URL,
        date(2020, 1, 1),
    )
    assert await repository.segments_by_ref([]) == []


async def test_full_text_search_ranks_by_shared_words_and_needs_only_one(repository):
    third = ParsedSegment(
        "R1(3)", "R1", "subsection", 1, ("Part 1",), "Students may study.", URL, date(2020, 1, 1)
    )
    document = replace(DOCUMENT, segments=(*DOCUMENT.segments, third))
    await ingest([SOURCE], FakeSourceReader({"regs": document}), repository)

    hits = await repository.full_text_search("can students work while their permits last?", 10)

    assert [hit.ref for hit in hits] == ["R1(2)", "R1(1)", "R1(3)"]
    assert [hit.ref for hit in await repository.full_text_search("students", 1)] == ["R1(2)"]
    assert await repository.full_text_search("the of and", 10) == []
    assert await repository.full_text_search("citizenship", 10) == []
