"""Compare POS access for explicitly selected accounts; never change role mappings."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import text
from app.core.database import SessionLocal
from app.models.user import User
from app.services.pos_access_review import review_pos_access


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--user-id', type=int, action='append', required=True)
    args = parser.parse_args()
    with SessionLocal() as db:
        if db.bind.dialect.name == 'postgresql':
            db.execute(text('SET TRANSACTION READ ONLY'))
        results=[]
        for user_id in dict.fromkeys(args.user_id):
            user=db.get(User,user_id)
            results.append(review_pos_access(db,user) if user else {'user_id':user_id,'error':'USER_NOT_FOUND'})
        print(json.dumps({'mode':'READ_ONLY','accounts':results},indent=2,default=str))
        db.rollback()
    print('READ ONLY: no users, roles, permissions, menus, transactions or balances changed.')


if __name__ == '__main__':
    main()
