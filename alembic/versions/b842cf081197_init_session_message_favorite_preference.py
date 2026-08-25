"""init session message favorite preference

Revision ID: b842cf081197
Revises: 
Create Date: 2026-08-25 23:17:05.768200

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b842cf081197'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'session',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('thread_id', sa.String(length=64), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_session_thread_id', 'session', ['thread_id'], unique=True)

    op.create_table(
        'message',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=16), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['session.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_message_session_id', 'message', ['session_id'], unique=False)

    op.create_table(
        'favorite',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('poi_id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_favorite_poi_id', 'favorite', ['poi_id'], unique=True)

    op.create_table(
        'preference',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('key', sa.String(length=32), nullable=False),
        sa.Column('value', sa.String(length=255), nullable=False),
        sa.Column('weight', sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key', 'value', name='uq_preference_key_value'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('preference')

    op.drop_index('ix_favorite_poi_id', table_name='favorite')
    op.drop_table('favorite')

    op.drop_index('ix_message_session_id', table_name='message')
    op.drop_table('message')

    op.drop_index('ix_session_thread_id', table_name='session')
    op.drop_table('session')
