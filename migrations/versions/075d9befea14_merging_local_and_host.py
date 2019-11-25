"""merging local and host

Revision ID: 075d9befea14
Revises: cad0b21cb9a5, 6afabe49da38
Create Date: 2019-11-25 18:58:11.381245

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '075d9befea14'
down_revision = ('cad0b21cb9a5', '6afabe49da38')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
