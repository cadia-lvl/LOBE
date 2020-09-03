"""empty message

Revision ID: 3fb71d18d6cf
Revises: 2ba5255eb0a6
Create Date: 2019-11-29 01:36:41.331329

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3fb71d18d6cf'
down_revision = '2ba5255eb0a6'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('Collection', sa.Column('active', sa.Boolean(), nullable=True))
    op.drop_column('Token', 'active')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('Token', sa.Column('active', sa.BOOLEAN(), autoincrement=False, nullable=True))
    op.drop_column('Collection', 'active')
    # ### end Alembic commands ###
