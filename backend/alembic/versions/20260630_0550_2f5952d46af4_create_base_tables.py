"""create base tables: users, articles, publish_logs, tasks

Revision ID: 2f5952d46af4
Revises: 000_init
Create Date: 2026-06-30 05:50:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "2f5952d46af4"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Base tables already created by 000_init — pass through"""
    pass


def downgrade() -> None:
    """Let 000_init handle downgrade"""
    pass
