"""Segments carry the official URL that citations link to.

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE segments ADD COLUMN url text")
    # Segments ingested before this column existed get their document's URL.
    op.execute(
        """
        UPDATE segments seg SET url = src.url
        FROM source_versions ver JOIN sources src ON src.id = ver.source_id
        WHERE ver.id = seg.version_id
        """
    )
    op.execute("ALTER TABLE segments ALTER COLUMN url SET NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE segments DROP COLUMN url")
