"""empty message

Revision ID: 317a951676a1
Revises: b1760222e5e1
Create Date: 2020-06-16 12:32:43.238508

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '317a951676a1'
down_revision = 'b1760222e5e1'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('trim',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('recording_id', sa.Integer(), nullable=True),
    sa.Column('start', sa.Float(), nullable=True),
    sa.Column('end', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['recording_id'], ['Recording.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('trim')
    # ### end Alembic commands ###
