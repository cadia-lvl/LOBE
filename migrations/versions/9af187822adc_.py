"""empty message

Revision ID: 9af187822adc
Revises: 75287632e523
Create Date: 2020-07-07 18:10:14.818730

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9af187822adc'
down_revision = '75287632e523'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('progression_icon',
    sa.Column('progression_id', sa.Integer(), nullable=True),
    sa.Column('icon_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['icon_id'], ['verifier_icon.id'], ),
    sa.ForeignKeyConstraint(['progression_id'], ['verifier_progression.id'], )
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('progression_icon')
    # ### end Alembic commands ###
