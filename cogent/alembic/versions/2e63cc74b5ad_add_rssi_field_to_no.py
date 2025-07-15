"""add rssi field to nodestate

Revision ID: 2e63cc74b5ad
Revises: 4f51a320d6b6
Create Date: 2013-02-18 11:18:20.052019

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "2e63cc74b5ad"
down_revision = "4f51a320d6b6"


def upgrade():
    op.add_column("NodeState", sa.Column("rssi", sa.Integer(), nullable=True))
    ### end Alembic commands ###


def downgrade():
    op.drop_column("NodeState", "rssi")
    ### end Alembic commands ###
