"""add sequence number to nodestate

Revision ID: 4f51a320d6b6
Revises: 1f9a02a1b28
Create Date: 2013-01-26 10:01:25.768500

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "4f51a320d6b6"
# down_revision = '1f9a02a1b28'
down_revision = "1414b56f7f1"


def upgrade():
    op.add_column("NodeState", sa.Column("seq_num", sa.Integer(), nullable=True))
    ### end Alembic commands ###


def downgrade():
    op.drop_column("NodeState", "seq_num")
    ### end Alembic commands ###
