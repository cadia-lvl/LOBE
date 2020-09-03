"""empty message

Revision ID: 2daf67ed4b63
Revises: 9806580aec8b
Create Date: 2020-07-08 18:27:02.989630

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2daf67ed4b63'
down_revision = '9806580aec8b'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('user', sa.Column('progression_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'user', 'verifier_progression', ['progression_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'user', type_='foreignkey')
    op.drop_column('user', 'progression_id')
    # ### end Alembic commands ###
