"""Add flag_shares table

Revision ID: c7d2e4f6a8b1
Revises: a3e1c5d7b9f2
Create Date: 2026-10-25 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c7d2e4f6a8b1"
down_revision = "a3e1c5d7b9f2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "flag_shares",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("challenge_id", sa.Integer(), nullable=True),
        sa.Column("flag_id", sa.Integer(), nullable=True),
        sa.Column("submission_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("owner_team_id", sa.Integer(), nullable=True),
        sa.Column("ip", sa.String(length=46), nullable=True),
        sa.Column("provided", sa.Text(), nullable=True),
        sa.Column("date", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["challenge_id"], ["challenges.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["flag_id"], ["flags.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["submission_id"], ["submissions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("flag_shares")
