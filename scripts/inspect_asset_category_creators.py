"""Read-only category authorship and usage report, before or after PPh migration."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import text, inspect
from app.core.database import SessionLocal
from app.services.asset_category_policy import LEGACY_SCRIPT_CODES


def main():
    with SessionLocal() as db:
        has_group='fiscal_group_code' in {c['name'] for c in inspect(db.get_bind()).get_columns('fixed_asset_categories')}
        fields='id,code,name,is_active,asset_account_id'+(',fiscal_group_code' if has_group else '')
        rows=[]
        for category in db.execute(text(f'SELECT {fields} FROM fixed_asset_categories ORDER BY code')).mappings():
            creator=db.execute(text("SELECT action,actor_name,created_at,details FROM audit_logs WHERE entity_type='FIXED_ASSET_CATEGORY' AND entity_id=:id AND action IN ('ASSET_CATEGORY_CREATED','CREATE') ORDER BY id LIMIT 1"),{'id':category['id']}).mappings().first()
            details=(creator['details'] or {}) if creator else {}
            if isinstance(details,str):details=json.loads(details)
            ours=bool(category['code'] in LEGACY_SCRIPT_CODES and creator and creator['action']=='ASSET_CATEGORY_CREATED' and details.get('batch')=='ASSET_POLICY_20261020')
            used=db.execute(text('SELECT count(*) FROM fixed_assets WHERE asset_category_id=:id'),{'id':category['id']}).scalar()
            rows.append({**dict(category),'creator':creator['actor_name'] if creator else None,'created_at':creator['created_at'] if creator else None,
                         'source':'MMH_SETUP_SCRIPT' if ours else 'USER_OR_UNCONFIRMED','assets_using_category':used})
        print(json.dumps({'mode':'READ_ONLY','categories':rows},indent=2,default=str))
        db.rollback()
    print('READ ONLY: no categories, assets, journals, profiles or balances changed.')


if __name__=='__main__':main()
