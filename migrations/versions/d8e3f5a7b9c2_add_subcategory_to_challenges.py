"""Add subcategory column to challenges

Revision ID: d8e3f5a7b9c2
Revises: c7d2e4f6a8b1
Create Date: 2026-10-26 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d8e3f5a7b9c2"
down_revision = "c7d2e4f6a8b1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "challenges", sa.Column("subcategory", sa.String(length=80), nullable=True)
    )


def downgrade():
    op.drop_column("challenges", "subcategory")
