"""Corpus: sources, versions and segments.

Revision ID: 0001
Revises:
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute(
        """
        CREATE TABLE sources (
            id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            slug            text NOT NULL UNIQUE,
            title           text NOT NULL,
            tier            smallint NOT NULL CHECK (tier IN (1, 2, 3)),
            kind            text NOT NULL,
            programs        text[] NOT NULL DEFAULT '{}',
            language        text NOT NULL,
            url             text NOT NULL,
            licence         text NOT NULL,
            last_checked_at timestamptz,
            created_at      timestamptz NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE source_versions (
            id           uuid PRIMARY KEY,
            seq          bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
            source_id    uuid NOT NULL REFERENCES sources (id),
            content_hash text NOT NULL,
            raw          bytea NOT NULL,
            captured_at  timestamptz NOT NULL,
            published_on date
        )
        """
    )
    op.execute("CREATE INDEX source_versions_source_seq ON source_versions (source_id, seq DESC)")

    # Versions are append-only (docs/architecture.md, section 8).
    op.execute(
        """
        CREATE FUNCTION source_versions_append_only() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'source_versions is append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER source_versions_append_only
        BEFORE UPDATE OR DELETE ON source_versions
        FOR EACH ROW EXECUTE FUNCTION source_versions_append_only()
        """
    )
    op.execute(
        """
        CREATE TRIGGER source_versions_no_truncate
        BEFORE TRUNCATE ON source_versions
        FOR EACH STATEMENT EXECUTE FUNCTION source_versions_append_only()
        """
    )

    # The full-text configuration follows the segment's language, so adding French
    # needs no restructuring.
    op.execute(
        """
        CREATE TABLE segments (
            id              uuid PRIMARY KEY,
            version_id      uuid NOT NULL REFERENCES source_versions (id),
            parent_id       uuid REFERENCES segments (id),
            ref             text NOT NULL,
            kind            text NOT NULL,
            depth           smallint NOT NULL,
            position        integer NOT NULL,
            heading_path    text[] NOT NULL,
            body            text NOT NULL,
            text_hash       text NOT NULL,
            last_amended_on date,
            language        text NOT NULL,
            is_current      boolean NOT NULL,
            embedding       vector(1024),
            tsv             tsvector GENERATED ALWAYS AS (
                to_tsvector(
                    CASE language
                        WHEN 'fr' THEN 'french'::regconfig
                        ELSE 'english'::regconfig
                    END,
                    body
                )
            ) STORED,
            UNIQUE (version_id, ref)
        )
        """
    )
    # Only current segments are searched (ADR 0001), so the search indexes are partial.
    op.execute("CREATE UNIQUE INDEX segments_current_ref ON segments (ref) WHERE is_current")
    op.execute("CREATE INDEX segments_current_tsv ON segments USING gin (tsv) WHERE is_current")
    op.execute(
        """
        CREATE INDEX segments_current_embedding ON segments
        USING hnsw (embedding vector_cosine_ops) WHERE is_current
        """
    )
    op.execute("CREATE INDEX segments_parent ON segments (parent_id)")


def downgrade() -> None:
    op.execute("DROP TABLE segments")
    op.execute("DROP TABLE source_versions")
    op.execute("DROP FUNCTION source_versions_append_only()")
    op.execute("DROP TABLE sources")
