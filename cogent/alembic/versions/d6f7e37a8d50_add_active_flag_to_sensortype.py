"""add active flag to sensortype

Revision ID: d6f7e37a8d50
Revises: 1e6b75bbade9
Create Date: 2025-08-27 12:02:01.261484

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = "d6f7e37a8d50"
down_revision = "1e6b75bbade9"


def upgrade():
    op.add_column(
        "SensorType",
        sa.Column("active", sa.Boolean(), nullable=False, server_default="0"),
    )
    conn = op.get_bind()
    conn.execute(
        text(
            "UPDATE SensorType SET active = 1 WHERE id IN (SELECT DISTINCT `type` FROM Reading)"
        )
    )


def downgrade():
    op.drop_column("SensorType", "active")
