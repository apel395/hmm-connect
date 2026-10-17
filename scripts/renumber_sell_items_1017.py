"""Replace legacy SELL group prefixes with 5/6/7/8, retaining IDs and source links."""
import argparse
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.item_group import ItemGroup
from app.models.product import Product
from app.services.item_code import lock_item_creation, next_item_code
from app.services.sell_item_groups import LEGACY_SELL_GROUP_CODES, sell_group_code
from app.services.audit import record_audit


def renumber(db, actor):
    lock_item_creation(db)
    groups = db.query(ItemGroup).order_by(ItemGroup.id).with_for_update().all()
    products = db.query(Product).filter(Product.item_type == 'SELL').order_by(Product.id).with_for_update().all()
    changes = []
    for group in groups:
        if group.item_type != 'SELL' or group.code not in LEGACY_SELL_GROUP_CODES:
            continue
        target = sell_group_code(group.code)
        if any(other.id != group.id and other.code == target for other in groups):
            raise ValueError(f'Group {target} is already registered; resolve the duplicate group before renumbering')
        before = {'code': group.code, 'name': group.name}
        group.code = target
        audit = record_audit(db, actor, 'SELL_GROUP_RENUMBERED', 'ITEM_GROUP',
                            f'Renumbered selling group {before["code"]} to {target}',
                            entity_id=group.id, before_data=before, after_data={'code': target, 'name': group.name})
        audit.source = 'EC2_SCRIPT'
        changes.append({'entity': 'GROUP', 'id': group.id, 'before': before['code'], 'after': target})
    for product in products:
        target = sell_group_code(product.group_code)
        legacy = re.fullmatch(r'(S-FOOD|S-BEV|S-SERVICE|S-ROOM)-(\d{6})', product.code.upper())
        if legacy:
            inferred = sell_group_code(legacy[1])
            if target in {'5', '6', '7', '8'} and target != inferred:
                raise ValueError(f'Item {product.id} has conflicting selling code and group')
            target = inferred
        before = {'code': product.code, 'group_code': product.group_code,
                  'subgroup_code': product.subgroup_code, 'subgroup_name': product.subgroup_name}
        new_code = product.code
        if legacy:
            desired = target + '-' + legacy[2]
            occupied = db.query(Product.id).filter(Product.code == desired, Product.id != product.id).first()
            new_code = next_item_code(db, target, '') if occupied else desired
        after = {'code': new_code, 'group_code': target, 'subgroup_code': '', 'subgroup_name': ''}
        if before == after:
            continue
        for key, value in after.items():
            setattr(product, key, value)
        audit = record_audit(db, actor, 'SELL_ITEM_RENUMBERED', 'PRODUCT',
                            f'Updated selling item code {before["code"]} to {new_code}',
                            entity_id=product.id, before_data=before, after_data=after)
        audit.source = 'EC2_SCRIPT'
        db.flush()  # The next item must see this allocation.
        changes.append({'entity': 'PRODUCT', 'id': product.id, 'before': before, 'after': after})
    db.flush()
    return changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--output', default='/tmp/sell-item-numbering.json')
    args = parser.parse_args()
    from app.core.database import SessionLocal
    actor = SimpleNamespace(id=None, username=None, full_name='EC2 selling item numbering operator',
                            roles=[SimpleNamespace(name='SYSTEM_ADMINISTRATOR')], audit_source='EC2_SCRIPT')
    with SessionLocal() as db:
        try:
            changes = renumber(db, actor)
            report = {'mode': 'APPLY' if args.apply else 'DRY_RUN', 'changes': changes,
                      'group_count': sum(r['entity'] == 'GROUP' for r in changes),
                      'item_count': sum(r['entity'] == 'PRODUCT' for r in changes)}
            Path(args.output).write_text(json.dumps(report, indent=2))
            if args.apply:
                db.commit()
            else:
                db.rollback()
            print(json.dumps({k: v for k, v in report.items() if k != 'changes'}, indent=2))
            print('Full report:', args.output)
            print('COMMITTED codes and audit records only.' if args.apply else 'DRY RUN: all changes rolled back. Use --apply to commit.')
            print('Record IDs, stock, transactions, tax, journals and opening balances unchanged.')
        except Exception:
            db.rollback()
            raise


if __name__ == '__main__':
    main()
