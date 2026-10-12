"""Ports the services depend on. Integrations implement them; tests use fakes."""

from collections.abc import Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.domain.corpus import ParsedDocument, Source, SourceStatus
from app.domain.retrieval import RetrievedSegment


class IngestAlreadyRunning(Exception):
    """Another ingest holds the lock."""


class SourceReader(Protocol):
    async def read(self, source: Source) -> tuple[bytes, ParsedDocument]:
        """Fetch a source and parse it. Returns the raw payload and its segments."""
        ...


class Embedder(Protocol):
    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class CorpusRepository(Protocol):
    def ingest_lock(self) -> AbstractAsyncContextManager[None]:
        """Hold the single ingest lock, or raise IngestAlreadyRunning."""
        ...

    async def upsert_source(self, source: Source) -> UUID: ...

    async def current_content_hash(self, source_id: UUID) -> str | None:
        """Content hash of the version whose segments are current, if there is one."""
        ...

    async def retire_missing(self, keep_slugs: Sequence[str]) -> list[str]:
        """Make the segments of every source not in `keep_slugs` non-current.

        Returns the slugs retired. Their versions are kept.
        """
        ...

    async def mark_checked(self, source_id: UUID, at: datetime) -> None: ...

    async def embedded_text_hashes(self, source_id: UUID) -> dict[str, str]:
        """Ref -> text hash, for the source's current segments that have an embedding."""
        ...

    async def add_version(
        self,
        source_id: UUID,
        source: Source,
        content_hash: str,
        raw: bytes,
        document: ParsedDocument,
        captured_at: datetime,
        embeddings: Mapping[str, list[float]],
    ) -> UUID:
        """Append a version and make its segments the current ones, atomically.

        Embeddings are keyed by ref. A segment without one keeps the previous version's
        embedding when its text hash is unchanged.
        """
        ...

    async def unembedded_current(self, limit: int) -> list[tuple[UUID, tuple[str, ...], str]]:
        """Current segments with text but no embedding: (id, heading path, body)."""
        ...

    async def set_embeddings(self, embeddings: Mapping[UUID, list[float]]) -> None: ...

    async def status(self) -> list[SourceStatus]: ...


class SegmentSearch(Protocol):
    """Finds current segments. Only current segments are ever searched (ADR 0001)."""

    async def segments_by_ref(self, refs: Sequence[str]) -> list[RetrievedSegment]:
        """The current segments with these refs, in the order given. Unknown refs are skipped."""
        ...

    async def full_text_search(self, query: str, limit: int) -> list[RetrievedSegment]:
        """Segments whose text shares words with the query, best match first."""
        ...
