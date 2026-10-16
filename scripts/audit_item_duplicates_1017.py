"""Read-only duplicate review; never merge/delete item history automatically."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def duplicate_groups(items):
    groups = defaultdict(list)
    for item in items:
        key = (item['catalog_type'], item['item_type'], re.sub(r'\s+', ' ', item['name'].strip()).casefold())
        groups[key].append(item)
    return [dict(catalog_type=k[0], item_type=k[1], normalized_name=k[2], items=rows,
                 action='REVIEW_REFERENCES_AND_UNITS_BEFORE_MERGE') for k, rows in groups.items() if len(rows)>1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='/tmp/item-duplicate-review.json')
    args=parser.parse_args()
    from app.core.database import SessionLocal
    from app.models.product import Product
    from sqlalchemy import inspect, text
    with SessionLocal() as db:
        items=[dict(id=p.id,code=p.code,name=p.name,catalog_type=p.catalog_type,item_type=p.item_type,
                    uom=p.uom,usage_uom=p.usage_uom,conversion=str(p.conversion),treatment=p.inventory_treatment,
                    is_active=p.is_active) for p in db.query(Product).order_by(Product.id)]
        groups=duplicate_groups(items)
        schema=inspect(db.connection())
        references=[]
        for table in schema.get_table_names():
            for fk in schema.get_foreign_keys(table):
                if fk.get('referred_table')=='products' and len(fk['constrained_columns'])==1:
                    references.append((table,fk['constrained_columns'][0]))
        quote=db.bind.dialect.identifier_preparer.quote
        for group in groups:
            for item in group['items']:
                item['references']={}
                for table,column in references:
                    count=db.execute(text(f'SELECT count(*) FROM {quote(table)} WHERE {quote(column)} = :id'),{'id':item['id']}).scalar_one()
                    if count:item['references'][table]=count
        report=dict(mode='READ_ONLY',items=len(items),duplicate_groups=len(groups),groups=groups)
        Path(args.output).write_text(json.dumps(report,indent=2))
        db.rollback()
    print(json.dumps(dict(mode='READ_ONLY',items=len(items),duplicate_groups=len(groups),output=args.output)))
    print('No items, source references, stock, journals or balances changed.')


if __name__=='__main__':main()
