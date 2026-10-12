"""Deterministic in-memory stand-ins for the ports. Used by tests; they touch no network."""

import hashlib
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from app.domain.corpus import ParsedDocument, Source, SourceStatus
from app.domain.hashing import text_hash
from app.domain.ports import IngestAlreadyRunning

EMBEDDING_DIMENSIONS = 1024


class FakeSourceReader:
    """Serves documents set by the test, keyed by source slug."""

    def __init__(self, documents: dict[str, ParsedDocument] | None = None) -> None:
        self.documents = documents or {}

    async def read(self, source: Source) -> tuple[bytes, ParsedDocument]:
        if source.slug not in self.documents:
            raise LookupError(f"no document for {source.slug}")
        return source.slug.encode(), self.documents[source.slug]


class FakeEmbedder:
    """Maps each text to a fixed vector derived from its hash, and records what it was asked."""

    def __init__(self) -> None:
        self.embedded: list[str] = []

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.embedded.extend(texts)
        return [self.vector(text) for text in texts]

    @staticmethod
    def vector(text: str) -> list[float]:
        digest = hashlib.sha256(text.encode()).digest()
        return [digest[i % len(digest)] / 255 for i in range(EMBEDDING_DIMENSIONS)]


@dataclass
class _Segment:
    id: UUID
    ref: str
    heading_path: tuple[str, ...]
    body: str
    text_hash: str
    embedding: list[float] | None


@dataclass
class _Version:
    id: UUID
    content_hash: str
    segments: list[_Segment]


@dataclass
class _SourceRow:
    id: UUID
    source: Source
    versions: list[_Version] = field(default_factory=list)
    last_checked_at: datetime | None = None
    retired: bool = False


class InMemoryCorpusRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, _SourceRow] = {}
        self._locked = False

    @asynccontextmanager
    async def ingest_lock(self) -> AsyncIterator[None]:
        if self._locked:
            raise IngestAlreadyRunning("another ingest is running")
        self._locked = True
        try:
            yield
        finally:
            self._locked = False

    async def upsert_source(self, source: Source) -> UUID:
        for row in self.rows.values():
            if row.source.slug == source.slug:
                row.source = source
                return row.id
        row = _SourceRow(uuid4(), source)
        self.rows[row.id] = row
        return row.id

    async def current_content_hash(self, source_id: UUID) -> str | None:
        row = self.rows[source_id]
        return row.versions[-1].content_hash if row.versions and not row.retired else None

    async def retire_missing(self, keep_slugs: Sequence[str]) -> list[str]:
        retired = []
        for row in self.rows.values():
            if row.source.slug not in keep_slugs and self.current(row.id):
                row.retired = True
                retired.append(row.source.slug)
        return sorted(retired)

    async def mark_checked(self, source_id: UUID, at: datetime) -> None:
        self.rows[source_id].last_checked_at = at

    async def embedded_text_hashes(self, source_id: UUID) -> dict[str, str]:
        return {s.ref: s.text_hash for s in self.current(source_id) if s.embedding is not None}

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
        previous = {s.ref: s for s in self.current(source_id)}
        segments = []
        for parsed in document.segments:
            hash_ = text_hash(parsed)
            embedding = embeddings.get(parsed.ref)
            old = previous.get(parsed.ref)
            if embedding is None and old is not None and old.text_hash == hash_:
                embedding = old.embedding
            segments.append(
                _Segment(uuid4(), parsed.ref, parsed.heading_path, parsed.body, hash_, embedding)
            )
        version = _Version(uuid4(), content_hash, segments)
        row = self.rows[source_id]
        row.versions.append(version)
        row.retired = False
        row.last_checked_at = captured_at
        return version.id

    async def unembedded_current(self, limit: int) -> list[tuple[UUID, tuple[str, ...], str]]:
        missing = [
            (s.id, s.heading_path, s.body)
            for source_id in self.rows
            for s in self.current(source_id)
            if s.embedding is None and s.body
        ]
        return missing[:limit]

    async def set_embeddings(self, embeddings: Mapping[UUID, list[float]]) -> None:
        for source_id in self.rows:
            for segment in self.current(source_id):
                if segment.id in embeddings:
                    segment.embedding = embeddings[segment.id]

    async def status(self) -> list[SourceStatus]:
        return [
            SourceStatus(
                slug=row.source.slug,
                authority=row.source.authority.value,
                versions=len(row.versions),
                current_segments=len(self.current(row.id)),
                unembedded_segments=sum(
                    1 for s in self.current(row.id) if s.embedding is None and s.body
                ),
                published_on=None,
                last_checked_at=row.last_checked_at,
            )
            for row in self.rows.values()
        ]

    def current(self, source_id: UUID) -> list[_Segment]:
        """The segments of the source's latest version, unless the source is retired."""
        row = self.rows[source_id]
        return row.versions[-1].segments if row.versions and not row.retired else []
