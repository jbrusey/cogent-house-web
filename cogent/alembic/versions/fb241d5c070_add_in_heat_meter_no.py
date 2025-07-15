"""add in heat meter nodetype

Revision ID: fb241d5c070
Revises: 579fffd63c6e
Create Date: 2013-11-26 10:36:32.481777

"""

from alembic import op
from sqlalchemy import DateTime, Integer, String
from sqlalchemy.sql import column, table

# revision identifiers, used by Alembic.
revision = "fb241d5c070"
down_revision = "579fffd63c6e"


def upgrade():
    nodetype = table(
        "NodeType",
        column("id", Integer),
        column("name", String(20)),
        column("time", DateTime),
        column("seq", Integer),
        column("updated_seq", Integer),
        column("period", Integer),
        column("blink", Integer),  # shouldbe tinyint
        column("configured", String(10)),
    )

    op.bulk_insert(
        nodetype,
        [
            {
                "id": 4,
                "name": "Heat Meter",
                "time": "2011-07-10 00:00:00",
                "seq": 1,
                "updated_seq": 0.0,
                "period": 307200.0,
                "blink": 0.0,
                "configured": "31,4",
            }
        ],
    )


def downgrade():
    pass
