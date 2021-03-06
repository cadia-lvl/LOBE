"""empty message

Revision ID: 88198f3b5133
Revises: 9af187822adc
Create Date: 2020-07-07 18:27:18.230082

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '88198f3b5133'
down_revision = '9af187822adc'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('verifier_icon', sa.Column('Font Awesome ID', sa.String(), nullable=True))
    op.drop_column('verifier_icon', 'fa_id')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('verifier_icon', sa.Column('fa_id', sa.VARCHAR(), autoincrement=False, nullable=True))
    op.drop_column('verifier_icon', 'Font Awesome ID')
    # ### end Alembic commands ###
