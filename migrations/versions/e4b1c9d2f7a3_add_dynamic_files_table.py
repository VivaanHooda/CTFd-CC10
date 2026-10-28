"""Add dynamic_files table

Revision ID: e4b1c9d2f7a3
Revises: d8e3f5a7b9c2
Create Date: 2026-10-28 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "e4b1c9d2f7a3"
down_revision = "d8e3f5a7b9c2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "dynamic_files",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("challenge_id", sa.Integer(), nullable=True),
        sa.Column("filename", sa.String(length=128), nullable=True),
        sa.Column("endpoint", sa.Text(), nullable=True),
        sa.Column("secret", sa.String(length=128), nullable=True),
        sa.Column("bind", sa.String(length=32), nullable=True),
        sa.Column("timeout", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["challenge_id"], ["challenges.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("dynamic_files")
