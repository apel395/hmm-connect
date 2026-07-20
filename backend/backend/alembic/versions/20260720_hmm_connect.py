"""fix trial emails and rename app to HMM Connect

Revision ID: 20260720_hmm_connect
Revises: 20260720_trial_users
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260720_hmm_connect"
down_revision: Union[str, Sequence[str], None] = "20260720_trial_users"
branch_labels = None
depends_on = None


EMAILS = {
    "admin": "admin@example.com",
    "requester": "requester@example.com",
    "purchasing": "purchasing@example.com",
    "warehouse": "warehouse@example.com",
    "finance": "finance@example.com",
    "manager": "manager@example.com",
}


def upgrade() -> None:
    conn = op.get_bind()

    for username, email in EMAILS.items():
        conn.execute(
            sa.text(
                """
                UPDATE users
                SET email = :email
                WHERE username = :username
                """
            ),
            {"username": username, "email": email},
        )


def downgrade() -> None:
    conn = op.get_bind()

    for username in EMAILS:
        conn.execute(
            sa.text(
                """
                UPDATE users
                SET email = :email
                WHERE username = :username
                """
            ),
            {
                "username": username,
                "email": f"{username}@erp.local",
            },
        )
