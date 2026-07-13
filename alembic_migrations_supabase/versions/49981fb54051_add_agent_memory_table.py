"""add agent_memory table

Revision ID: 49981fb54051
Revises: 
Create Date: 2026-07-13 11:56:05.246191

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import VECTOR

# revision identifiers, used by Alembic.
revision: str = '49981fb54051'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('agent_memory',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('course_id', sa.String(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'),
                  nullable=True),
        sa.Column('course_outline', sa.Text(), nullable=True),
        sa.Column('course_outline_embeddings', VECTOR(1536), nullable=True),
        sa.Column('course_content', sa.Text(), nullable=True),
        sa.Column('course_content_embeddings', VECTOR(1536), nullable=True),
        sa.Column('final_course', sa.Text(), nullable=True),
        sa.Column('final_course_outline', sa.Text(), nullable=True),
        sa.Column('final_course_outline_embeddings', VECTOR(1536), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'course_id', name='uq_agent_memory_user_course')
    )
    # NOTE: checkpoint_writes / checkpoints intentionally NOT dropped here.
    # Autogenerate flagged them as "orphaned" because they're created via
    # raw SQL in SupabaseCheckpointSaver.setup(), not SQLAlchemy models,
    # so they're invisible to target_metadata. They hold live thread state
    # — do not let a future autogenerate silently drop them either.


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('agent_memory')
