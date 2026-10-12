"""Authority levels replace tiers; segments gain an anchor and their outgoing links.

Revision ID: 0003
Revises: 0002
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Named levels, ranked. A new level is a row here, not a renumbering of every source.
    op.execute(
        """
        CREATE TABLE authority_levels (
            name text PRIMARY KEY,
            rank smallint NOT NULL UNIQUE
        )
        """
    )
    op.execute(
        """
        INSERT INTO authority_levels (name, rank) VALUES
            ('act', 1),
            ('regulations', 2),
            ('ministerial_instructions', 3),
            ('officer_instructions', 4),
            ('public_guidance', 5)
        """
    )
    op.execute("ALTER TABLE sources ADD COLUMN authority text REFERENCES authority_levels (name)")
    op.execute(
        """
        UPDATE sources SET authority = CASE
            WHEN tier = 1 AND url ILIKE '%/SOR-%' THEN 'regulations'
            WHEN tier = 1 THEN 'act'
            WHEN tier = 2 THEN 'officer_instructions'
            ELSE 'public_guidance'
        END
        """
    )
    op.execute("ALTER TABLE sources ALTER COLUMN authority SET NOT NULL")
    op.execute("ALTER TABLE sources DROP COLUMN tier")

    # The publisher's own id for the segment, which incoming links carry as a fragment.
    op.execute("ALTER TABLE segments ADD COLUMN anchor text")

    # Links name their target by ref and address, never by row: a target gets a new row
    # with every version, and most targets are not in the corpus at all.
    op.execute(
        """
        CREATE TABLE segment_links (
            segment_id      uuid NOT NULL REFERENCES segments (id),
            position        integer NOT NULL,
            origin          text NOT NULL
                            CHECK (origin IN ('html_link', 'xml_xref', 'text_mention')),
            link_text       text NOT NULL,
            target_url      text NOT NULL,
            target_fragment text,
            target_class    text NOT NULL,
            target_ref      text,
            PRIMARY KEY (segment_id, position)
        )
        """
    )
    op.execute("CREATE INDEX segment_links_target_ref ON segment_links (target_ref)")
    op.execute("CREATE INDEX segment_links_target_url ON segment_links (target_url)")


def downgrade() -> None:
    op.execute("DROP TABLE segment_links")
    op.execute("ALTER TABLE segments DROP COLUMN anchor")
    op.execute("ALTER TABLE sources ADD COLUMN tier smallint")
    op.execute(
        """
        UPDATE sources SET tier = CASE authority
            WHEN 'act' THEN 1 WHEN 'regulations' THEN 1
            WHEN 'officer_instructions' THEN 2 WHEN 'ministerial_instructions' THEN 2
            ELSE 3
        END
        """
    )
    op.execute("ALTER TABLE sources ALTER COLUMN tier SET NOT NULL")
    op.execute("ALTER TABLE sources DROP COLUMN authority")
    op.execute("DROP TABLE authority_levels")
