"""Postgres implementation of the corpus repository. The schema lives in migrations/."""

from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.domain.corpus import ParsedDocument, Source, SourceStatus
from app.domain.hashing import text_hash
from app.domain.ports import IngestAlreadyRunning

# Arbitrary constant identifying the ingest job to pg_advisory_lock.
INGEST_LOCK_KEY = 0x696D6D69


def create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url)


def _vector(embedding: list[float] | None) -> str | None:
    return None if embedding is None else "[" + ",".join(map(str, embedding)) + "]"


class PostgresCorpusRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    @asynccontextmanager
    async def ingest_lock(self) -> AsyncIterator[None]:
        # The lock belongs to this connection's session, so it is held open for the job.
        async with self._engine.connect() as conn:
            acquired = await conn.scalar(
                text("SELECT pg_try_advisory_lock(:key)"), {"key": INGEST_LOCK_KEY}
            )
            await conn.commit()
            if not acquired:
                raise IngestAlreadyRunning("another ingest is running")
            try:
                yield
            finally:
                await conn.execute(
                    text("SELECT pg_advisory_unlock(:key)"), {"key": INGEST_LOCK_KEY}
                )
                await conn.commit()

    async def upsert_source(self, source: Source) -> UUID:
        async with self._engine.begin() as conn:
            return await conn.scalar(
                text(
                    """
                    INSERT INTO sources
                        (slug, title, authority, kind, programs, language, url, licence)
                    VALUES (:slug, :title, :authority, :kind, CAST(:programs AS text[]),
                            :language, :url, :licence)
                    ON CONFLICT (slug) DO UPDATE SET
                        title = EXCLUDED.title, authority = EXCLUDED.authority,
                        kind = EXCLUDED.kind,
                        programs = EXCLUDED.programs, language = EXCLUDED.language,
                        url = EXCLUDED.url, licence = EXCLUDED.licence
                    RETURNING id
                    """
                ),
                {
                    "slug": source.slug,
                    "title": source.title,
                    "authority": source.authority.value,
                    "kind": source.kind.value,
                    "programs": list(source.programs),
                    "language": source.language,
                    "url": source.url,
                    "licence": source.licence,
                },
            )

    async def current_content_hash(self, source_id: UUID) -> str | None:
        async with self._engine.connect() as conn:
            return await conn.scalar(
                text(
                    """
                    SELECT v.content_hash FROM source_versions v
                    WHERE v.source_id = :source_id
                      AND EXISTS (
                          SELECT 1 FROM segments s WHERE s.version_id = v.id AND s.is_current
                      )
                    ORDER BY v.seq DESC LIMIT 1
                    """
                ),
                {"source_id": source_id},
            )

    async def retire_missing(self, keep_slugs: Sequence[str]) -> list[str]:
        async with self._engine.begin() as conn:
            rows = await conn.execute(
                text(
                    """
                    WITH retired AS (
                        UPDATE segments seg SET is_current = false
                        FROM source_versions ver
                        JOIN sources src ON src.id = ver.source_id
                        WHERE seg.version_id = ver.id
                          AND seg.is_current
                          AND src.slug <> ALL (CAST(:keep AS text[]))
                        RETURNING src.slug
                    )
                    SELECT DISTINCT slug FROM retired ORDER BY slug
                    """
                ),
                {"keep": list(keep_slugs)},
            )
            return [slug for (slug,) in rows]

    async def mark_checked(self, source_id: UUID, at: datetime) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(
                text("UPDATE sources SET last_checked_at = :at WHERE id = :id"),
                {"at": at, "id": source_id},
            )

    async def embedded_text_hashes(self, source_id: UUID) -> dict[str, str]:
        async with self._engine.connect() as conn:
            rows = await conn.execute(
                text(
                    """
                    SELECT s.ref, s.text_hash FROM segments s
                    JOIN source_versions v ON v.id = s.version_id
                    WHERE v.source_id = :source_id AND s.is_current AND s.embedding IS NOT NULL
                    """
                ),
                {"source_id": source_id},
            )
            return {ref: hash_ for ref, hash_ in rows}

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
        version_id = uuid4()
        ids = {segment.ref: uuid4() for segment in document.segments}
        rows = [
            {
                "id": ids[s.ref],
                "version_id": version_id,
                "parent_id": ids[s.parent_ref] if s.parent_ref else None,
                "ref": s.ref,
                "kind": s.kind,
                "depth": s.depth,
                "position": position,
                "heading_path": list(s.heading_path),
                "body": s.body,
                "url": s.url,
                "anchor": s.anchor,
                "text_hash": text_hash(s),
                "last_amended_on": s.last_amended_on,
                "language": source.language,
                "embedding": _vector(embeddings.get(s.ref)),
            }
            for position, s in enumerate(document.segments)
        ]
        links = [
            {
                "segment_id": ids[s.ref],
                "position": position,
                "origin": link.origin.value,
                "link_text": link.text,
                "target_url": link.target_url,
                "target_fragment": link.target_fragment,
                "target_class": link.target_class.value,
                "target_ref": link.target_ref,
            }
            for s in document.segments
            for position, link in enumerate(s.links)
        ]
        # One transaction: readers see the old version or the new one, never a mix.
        async with self._engine.begin() as conn:
            previous_version_id = await conn.scalar(
                text(
                    """
                    SELECT id FROM source_versions
                    WHERE source_id = :source_id ORDER BY seq DESC LIMIT 1
                    """
                ),
                {"source_id": source_id},
            )
            await conn.execute(
                text(
                    """
                    INSERT INTO source_versions
                        (id, source_id, content_hash, raw, captured_at, published_on)
                    VALUES (:id, :source_id, :content_hash, :raw, :captured_at, :published_on)
                    """
                ),
                {
                    "id": version_id,
                    "source_id": source_id,
                    "content_hash": content_hash,
                    "raw": raw,
                    "captured_at": captured_at,
                    "published_on": document.published_on,
                },
            )
            await conn.execute(
                text(
                    """
                    UPDATE segments SET is_current = false
                    WHERE is_current AND version_id IN (
                        SELECT id FROM source_versions WHERE source_id = :source_id
                    )
                    """
                ),
                {"source_id": source_id},
            )
            await conn.execute(
                text(
                    """
                    INSERT INTO segments
                        (id, version_id, parent_id, ref, kind, depth, position, heading_path,
                         body, url, anchor, text_hash, last_amended_on, language, is_current,
                         embedding)
                    VALUES
                        (:id, :version_id, :parent_id, :ref, :kind, :depth, :position,
                         CAST(:heading_path AS text[]), :body, :url, :anchor, :text_hash,
                         :last_amended_on, :language, true, CAST(:embedding AS vector))
                    """
                ),
                rows,
            )
            if links:
                await conn.execute(
                    text(
                        """
                        INSERT INTO segment_links
                            (segment_id, position, origin, link_text, target_url,
                             target_fragment, target_class, target_ref)
                        VALUES
                            (:segment_id, :position, :origin, :link_text, :target_url,
                             :target_fragment, :target_class, :target_ref)
                        """
                    ),
                    links,
                )
            if previous_version_id is not None:
                await conn.execute(
                    text(
                        """
                        UPDATE segments new SET embedding = old.embedding
                        FROM segments old
                        WHERE new.version_id = :version_id
                          AND old.version_id = :previous_version_id
                          AND old.ref = new.ref
                          AND old.text_hash = new.text_hash
                          AND new.embedding IS NULL
                          AND old.embedding IS NOT NULL
                        """
                    ),
                    {"version_id": version_id, "previous_version_id": previous_version_id},
                )
            await conn.execute(
                text("UPDATE sources SET last_checked_at = :at WHERE id = :id"),
                {"at": captured_at, "id": source_id},
            )
        return version_id

    async def unembedded_current(self, limit: int) -> list[tuple[UUID, tuple[str, ...], str]]:
        async with self._engine.connect() as conn:
            rows = await conn.execute(
                text(
                    """
                    SELECT id, heading_path, body FROM segments
                    WHERE is_current AND embedding IS NULL AND body <> ''
                    ORDER BY id LIMIT :limit
                    """
                ),
                {"limit": limit},
            )
            return [(id_, tuple(path), body) for id_, path, body in rows]

    async def set_embeddings(self, embeddings: Mapping[UUID, list[float]]) -> None:
        if not embeddings:
            return
        async with self._engine.begin() as conn:
            await conn.execute(
                text("UPDATE segments SET embedding = CAST(:embedding AS vector) WHERE id = :id"),
                [{"id": id_, "embedding": _vector(v)} for id_, v in embeddings.items()],
            )

    async def status(self) -> list[SourceStatus]:
        async with self._engine.connect() as conn:
            rows = await conn.execute(
                text(
                    """
                    SELECT
                        src.slug,
                        src.authority,
                        (SELECT count(*) FROM source_versions v WHERE v.source_id = src.id),
                        count(seg.id),
                        count(seg.id) FILTER (WHERE seg.embedding IS NULL AND seg.body <> ''),
                        max(ver.published_on),
                        src.last_checked_at
                    FROM sources src
                    JOIN authority_levels lvl ON lvl.name = src.authority
                    LEFT JOIN source_versions ver ON ver.source_id = src.id
                    LEFT JOIN segments seg ON seg.version_id = ver.id AND seg.is_current
                    GROUP BY src.id, lvl.rank
                    ORDER BY lvl.rank, src.slug
                    """
                )
            )
            return [SourceStatus(*row) for row in rows]
