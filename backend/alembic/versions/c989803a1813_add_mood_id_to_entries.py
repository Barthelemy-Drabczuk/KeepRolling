"""add mood_id to entries

Revision ID: c989803a1813
Revises: 2ddde1e33f3d
Create Date: 2026-08-25 14:10:20.907609

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c989803a1813"
down_revision: Union[str, Sequence[str], None] = "2ddde1e33f3d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("entries", sa.Column("mood_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_entries_mood_id_moods", "entries", "moods", ["mood_id"], ["id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("fk_entries_mood_id_moods", "entries", type_="foreignkey")
    op.drop_column("entries", "mood_id")
