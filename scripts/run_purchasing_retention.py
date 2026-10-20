"""EC2 purchasing age cleanup. Preview by default; --apply commits atomically."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    from sqlalchemy import text
    from app.core.database import SessionLocal
    from app.services.purchasing_retention import cleanup
    with SessionLocal() as db:
        if args.apply and db.bind.dialect.name=='postgresql':
            if not db.execute(text('SELECT pg_try_advisory_xact_lock(20261020, 17)')).scalar():
                print('Another purchasing cleanup is running. No changes.');return
        report=cleanup(db,apply=args.apply)
        if args.apply:db.commit()
        else:db.rollback()
        print(json.dumps(report,indent=2))
        print('COMMITTED purchasing cleanup; source accounting unchanged.' if args.apply else 'DRY RUN: no writes.')

if __name__=='__main__':main()
