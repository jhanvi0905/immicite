"""Ingest: pull sources into the corpus as versioned segments (docs/architecture.md 3.1)."""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from app.domain.corpus import ParsedDocument, Source, embedding_text
from app.domain.hashing import content_hash, text_hash
from app.domain.ports import CorpusRepository, Embedder, SourceReader

logger = logging.getLogger(__name__)

EMBED_BATCH_SIZE = 64


class Outcome(StrEnum):
    CREATED = "created"
    UNCHANGED = "unchanged"
    DRY_RUN = "dry_run"
    FAILED = "failed"


@dataclass(frozen=True)
class SourceResult:
    slug: str
    outcome: Outcome
    segments: int = 0
    error: str | None = None


async def ingest(
    sources: Sequence[Source],
    reader: SourceReader,
    repository: CorpusRepository,
    embedder: Embedder | None = None,
    *,
    dry_run: bool = False,
) -> list[SourceResult]:
    """Ingest each source in turn. One source failing does not stop the others.

    Raises IngestAlreadyRunning when another ingest holds the lock. A dry run fetches and
    parses but writes nothing, so it takes no lock.
    """
    if dry_run:
        return [await _ingest_guarded(s, reader, repository, embedder, dry_run) for s in sources]
    async with repository.ingest_lock():
        return [await _ingest_guarded(s, reader, repository, embedder, dry_run) for s in sources]


async def _ingest_guarded(
    source: Source,
    reader: SourceReader,
    repository: CorpusRepository,
    embedder: Embedder | None,
    dry_run: bool,
) -> SourceResult:
    try:
        result = await _ingest_source(source, reader, repository, embedder, dry_run)
    except Exception as exc:
        logger.exception("ingest failed for %s", source.slug)
        return SourceResult(source.slug, Outcome.FAILED, error=f"{type(exc).__name__}: {exc}")
    logger.info("%s: %s (%d segments)", source.slug, result.outcome, result.segments)
    return result


async def _ingest_source(
    source: Source,
    reader: SourceReader,
    repository: CorpusRepository,
    embedder: Embedder | None,
    dry_run: bool,
) -> SourceResult:
    raw, document = await reader.read(source)
    if not document.segments:
        # An empty parse means the source or the parser broke. Never replace a corpus with it.
        raise ValueError("parsed no segments")
    count = len(document.segments)
    if dry_run:
        return SourceResult(source.slug, Outcome.DRY_RUN, count)

    now = datetime.now(UTC)
    new_hash = content_hash(document)
    source_id = await repository.upsert_source(source)
    if await repository.current_content_hash(source_id) == new_hash:
        await repository.mark_checked(source_id, now)
        return SourceResult(source.slug, Outcome.UNCHANGED, count)

    embeddings: dict[str, list[float]] = {}
    if embedder is not None:
        embeddings = await _embed_changed(source_id, document, repository, embedder)
    await repository.add_version(source_id, source, new_hash, raw, document, now, embeddings)
    return SourceResult(source.slug, Outcome.CREATED, count)


async def retire_removed(manifest: Sequence[Source], repository: CorpusRepository) -> list[str]:
    """Take sources that left the manifest out of the searchable corpus. History is kept."""
    async with repository.ingest_lock():
        retired = await repository.retire_missing([source.slug for source in manifest])
    for slug in retired:
        logger.info("%s: retired, no longer in the manifest", slug)
    return retired


async def _embed_changed(
    source_id, document: ParsedDocument, repository: CorpusRepository, embedder: Embedder
) -> dict[str, list[float]]:
    """Embed only segments whose text changed; the rest reuse their stored embedding."""
    embedded = await repository.embedded_text_hashes(source_id)
    changed = [s for s in document.segments if s.body and embedded.get(s.ref) != text_hash(s)]
    embeddings: dict[str, list[float]] = {}
    for start in range(0, len(changed), EMBED_BATCH_SIZE):
        batch = changed[start : start + EMBED_BATCH_SIZE]
        vectors = await embedder.embed([embedding_text(s.heading_path, s.body) for s in batch])
        embeddings.update({s.ref: v for s, v in zip(batch, vectors, strict=True)})
    return embeddings


async def embed_missing(repository: CorpusRepository, embedder: Embedder) -> int:
    """Embed current segments that have none, for a corpus ingested without an embedder."""
    total = 0
    while rows := await repository.unembedded_current(EMBED_BATCH_SIZE):
        vectors = await embedder.embed([embedding_text(path, body) for _, path, body in rows])
        await repository.set_embeddings(
            {segment_id: v for (segment_id, _, _), v in zip(rows, vectors, strict=True)}
        )
        total += len(rows)
    return total
