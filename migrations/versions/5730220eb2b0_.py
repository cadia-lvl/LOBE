"""empty message

Revision ID: 5730220eb2b0
Revises: 759cd04e2408
Create Date: 2020-07-09 13:54:07.125299

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5730220eb2b0'
down_revision = '759cd04e2408'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('verifier_quote', sa.Column('rarity', sa.Integer(), nullable=True))
    op.add_column('verifier_title', sa.Column('rarity', sa.Integer(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('verifier_title', 'rarity')
    op.drop_column('verifier_quote', 'rarity')
    # ### end Alembic commands ###
