#!/usr/bin/env python3
"""Create or update the demo login account in the configured demo database.

Run this only on the EC2 administration host. It refuses to run unless
DEMO_DATABASE_URL points to a database different from DATABASE_URL and the
operator passes --confirm-demo-database.
"""

from __future__ import annotations

import argparse
import getpass
import os
from urllib.parse import urlsplit

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import DATABASE_URL
from app.core.db_scope import DEMO_DB_KEY, normalize_db_key
from app.core.security import hash_password
from app.models.role import Role
from app.models.user import User


def _database_name(url: str) -> str:
    return urlsplit(url).path.lstrip("/").split("/", 1)[0]


def _require_demo_target() -> str:
    url = settings.DEMO_DATABASE_URL
    if not url:
        raise SystemExit("DEMO_DATABASE_URL is required to seed the demo account")
    if url == DATABASE_URL or _database_name(url) == _database_name(DATABASE_URL):
        raise SystemExit("DEMO_DATABASE_URL must point to a separate demo database")
    normalize_db_key(DEMO_DB_KEY)
    return url


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", default=os.getenv("DEMO_USERNAME"))
    parser.add_argument("--email", default=None)
    parser.add_argument("--full-name", default="Demo User")
    parser.add_argument("--role", default="SYSTEM_ADMINISTRATOR")
    parser.add_argument(
        "--confirm-demo-database",
        action="store_true",
        help="required acknowledgement that the target is the demo database",
    )
    parser.add_argument(
        "--allow-weak-password",
        action="store_true",
        help="allow a short demo-only password; never use for primary accounts",
    )
    args = parser.parse_args()

    if not args.confirm_demo_database:
        parser.error("pass --confirm-demo-database to seed the demo account")
    if not args.username:
        parser.error("--username or DEMO_USERNAME is required")
    if args.username not in settings.demo_usernames:
        parser.error(
            f"{args.username!r} is not in DEMO_USERNAMES; demo login routing would not use it"
        )

    password = os.getenv("DEMO_PASSWORD") or getpass.getpass("Demo password: ")
    if len(password) < 8 and not args.allow_weak_password:
        parser.error(
            "demo password must be at least 8 characters; "
            "pass --allow-weak-password only for short demo-only credentials"
        )

    url = _require_demo_target()
    email = args.email or f"{args.username}@hmm.demo"
    engine = create_engine(url, future=True)

    with Session(engine) as db:
        role = db.scalar(select(Role).where(Role.name == args.role))
        if role is None:
            role = Role(name=args.role, description="Demo workspace access")
            db.add(role)
            db.flush()

        user = db.scalar(select(User).where(User.username == args.username))
        if user is None:
            user = User(
                username=args.username,
                email=email,
                full_name=args.full_name,
                password_hash=hash_password(password),
                is_active=True,
            )
            db.add(user)
            db.flush()
            action = "created"
        else:
            user.email = email
            user.full_name = args.full_name
            user.password_hash = hash_password(password)
            user.is_active = True
            user.active_session_id = None
            user.session_last_activity_at = None
            action = "updated"

        if role not in user.roles:
            user.roles.append(role)

        db.commit()

    engine.dispose()
    print(
        f"Demo account {args.username!r} {action} in demo database; "
        f"role={args.role}; primary database untouched."
    )


if __name__ == "__main__":
    main()
