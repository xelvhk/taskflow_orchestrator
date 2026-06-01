"""add video draft task type

Revision ID: 0002_add_video_draft_task_type
Revises: 0001_initial_schema
Create Date: 2026-06-01
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_add_video_draft_task_type"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE tasktype ADD VALUE IF NOT EXISTS 'VIDEO_DRAFT'")


def downgrade() -> None:
    # PostgreSQL cannot drop enum values directly without recreating the type.
    # Leaving this as a no-op preserves existing rows safely.
    pass
