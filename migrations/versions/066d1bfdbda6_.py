"""empty message

Revision ID: 066d1bfdbda6
Revises: 26eb1d59ef5d
Create Date: 2020-07-08 15:57:07.431545

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '066d1bfdbda6'
down_revision = '26eb1d59ef5d'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('verifier_icon', sa.Column('color', sa.Integer(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('verifier_icon', 'color')
    # ### end Alembic commands ###
