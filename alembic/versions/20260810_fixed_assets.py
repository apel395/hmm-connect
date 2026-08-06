"""Fixed assets and depreciation foundation.

Revision ID: 20260810_fixed_assets
Revises: 20260809_budget_hardening
"""
from alembic import op
from app.models.fixed_asset import FixedAssetCategory, FixedAsset, FixedAssetDepreciationSchedule, FixedAssetMovement, FixedAssetDepreciationRun

revision = "20260810_fixed_assets"
down_revision = "20260809_budget_hardening"
branch_labels = None
depends_on = None

TABLES = [
    FixedAssetCategory.__table__, FixedAsset.__table__,
    FixedAssetDepreciationSchedule.__table__, FixedAssetMovement.__table__,
    FixedAssetDepreciationRun.__table__,
]

def upgrade():
    bind = op.get_bind()
    for table in TABLES:
        table.create(bind, checkfirst=True)

def downgrade():
    bind = op.get_bind()
    for table in reversed(TABLES):
        table.drop(bind, checkfirst=True)
