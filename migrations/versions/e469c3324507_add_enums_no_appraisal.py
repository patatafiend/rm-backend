"""add_enums_no_appraisal

Revision ID: e469c3324507
Revises: a940066515fc
Create Date: 2026-07-18 11:42:39.183197

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e469c3324507'
down_revision: Union[str, None] = 'a940066515fc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE performance_appraisals "
        "MODIFY COLUMN third_month_decision "
        "ENUM('PROCEED_5TH', 'NON_REGULARIZATION', 'NO_APPRAISAL')"
    )
    op.execute(
        "ALTER TABLE performance_appraisals "
        "MODIFY COLUMN fifth_month_decision "
        "ENUM('REGULARIZATION', 'NON_REGULARIZATION', 'EXTENSION', 'NO_APPRAISAL')"
    )


def downgrade() -> None:
    # Any row already holding 'NO_APPRAISAL' in either column will be
    # silently truncated to '' by MySQL once removed from the enum —
    # reassign or back up those rows first if this has been live for a while.
    op.execute(
        "ALTER TABLE performance_appraisals "
        "MODIFY COLUMN fifth_month_decision "
        "ENUM('REGULARIZATION', 'NON_REGULARIZATION', 'EXTENSION')"
    )
    op.execute(
        "ALTER TABLE performance_appraisals "
        "MODIFY COLUMN third_month_decision "
        "ENUM('PROCEED_5TH', 'NON_REGULARIZATION')"
    )
