"""empty message

Revision ID: 75287632e523
Revises: 59632726c183
Create Date: 2020-07-07 18:07:55.588736

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '75287632e523'
down_revision = '59632726c183'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('verifier_icon',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('fa_id', sa.String(), nullable=True),
    sa.Column('title', sa.String(length=64), nullable=True),
    sa.Column('description', sa.String(length=255), nullable=True),
    sa.Column('price', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('verifier_progression',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('num_verifies', sa.Integer(), nullable=True),
    sa.Column('num_invalid', sa.Integer(), nullable=True),
    sa.Column('lobe_coins', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('verifier_progression')
    op.drop_table('verifier_icon')
    # ### end Alembic commands ###
