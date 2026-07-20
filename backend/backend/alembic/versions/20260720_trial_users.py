"""seed trial roles and users

Revision ID: 20260720_trial_users
Revises: 20260720_identity_context
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260720_trial_users"
down_revision: Union[str, Sequence[str], None] = "20260720_identity_context"
branch_labels = None
depends_on = None


TRIAL_USERS = [
    {
        "username": "admin",
        "email": "admin@example.com",
        "full_name": "ERP Administrator",
        "password_hash": "$2b$12$bGPrFxFsGlWDdR0OII5SUe08jLRONE01m1JzbK0kyCCQsD3nEddl.",
        "department": "MANAGEMENT",
        "location": "JKT",
        "role": "ADMIN",
    },
    {
        "username": "requester",
        "email": "requester@example.com",
        "full_name": "Trial Requester",
        "password_hash": "$2b$12$jFnM3iNhYxhmw48EGZ8Yoe8qEFl44X2fXcQZkXgSr1uHkwiZcAYDW",
        "department": "OPERATIONS",
        "location": "JKT",
        "role": "REQUESTER",
    },
    {
        "username": "purchasing",
        "email": "purchasing@example.com",
        "full_name": "Trial Purchasing",
        "password_hash": "$2b$12$jML7PePEfIL1r8yrK0r5mOu/ArdRbBwjpXybk6cYakA1KyCfwGFwy",
        "department": "PURCHASING",
        "location": "JKT",
        "role": "PURCHASING",
    },
    {
        "username": "warehouse",
        "email": "warehouse@example.com",
        "full_name": "Trial Warehouse",
        "password_hash": "$2b$12$hfk4ADV78iJVEemSJNnybe2yPF2hOE2EIDoILlTLTiseBduGDDhKi",
        "department": "WAREHOUSE",
        "location": "WH-JKT",
        "role": "WAREHOUSE",
    },
    {
        "username": "finance",
        "email": "finance@example.com",
        "full_name": "Trial Finance",
        "password_hash": "$2b$12$uk3.ThJctHLKzaMVN7nsperhONuhzvxZSeFiiXCzNUprvEK2sA5iK",
        "department": "FINANCE",
        "location": "JKT",
        "role": "FINANCE",
    },
    {
        "username": "manager",
        "email": "manager@example.com",
        "full_name": "Trial Manager",
        "password_hash": "$2b$12$rBHOsqTCBiuRjqOdSsnFT.etT6RukliQuH5igmo3do2LBqhbR3/wC",
        "department": "MANAGEMENT",
        "location": "JKT",
        "role": "MANAGER",
    },
]


ROLES = [
    ("ADMIN", "Full system administration"),
    ("REQUESTER", "Create and manage purchase requisitions"),
    ("PURCHASING", "Create and manage purchase orders"),
    ("WAREHOUSE", "Receive goods and manage warehouse stock"),
    ("FINANCE", "Manage finance and account payable workflows"),
    ("MANAGER", "Review and approve business transactions"),
]


def upgrade() -> None:
    conn = op.get_bind()

    for name, description in ROLES:
        conn.execute(
            sa.text(
                """
                INSERT INTO roles (name, description)
                VALUES (:name, :description)
                ON CONFLICT (name) DO UPDATE
                SET description = EXCLUDED.description
                """
            ),
            {"name": name, "description": description},
        )

    for trial_user in TRIAL_USERS:
        department_id = conn.execute(
            sa.text("SELECT id FROM departments WHERE code = :code"),
            {"code": trial_user["department"]},
        ).scalar_one()

        location_id = conn.execute(
            sa.text("SELECT id FROM locations WHERE code = :code"),
            {"code": trial_user["location"]},
        ).scalar_one()

        role_id = conn.execute(
            sa.text("SELECT id FROM roles WHERE name = :name"),
            {"name": trial_user["role"]},
        ).scalar_one()

        user_id = conn.execute(
            sa.text("SELECT id FROM users WHERE username = :username"),
            {"username": trial_user["username"]},
        ).scalar_one_or_none()

        if user_id is None:
            user_id = conn.execute(
                sa.text(
                    """
                    INSERT INTO users
                        (username, email, full_name, password_hash, is_active, department_id, location_id)
                    VALUES
                        (:username, :email, :full_name, :password_hash, true, :department_id, :location_id)
                    RETURNING id
                    """
                ),
                {
                    **trial_user,
                    "department_id": department_id,
                    "location_id": location_id,
                },
            ).scalar_one()
        else:
            conn.execute(
                sa.text(
                    """
                    UPDATE users
                    SET email = :email,
                        full_name = :full_name,
                        password_hash = :password_hash,
                        is_active = true,
                        department_id = :department_id,
                        location_id = :location_id
                    WHERE id = :user_id
                    """
                ),
                {
                    **trial_user,
                    "department_id": department_id,
                    "location_id": location_id,
                    "user_id": user_id,
                },
            )

        conn.execute(
            sa.text(
                """
                INSERT INTO user_roles (user_id, role_id)
                VALUES (:user_id, :role_id)
                ON CONFLICT DO NOTHING
                """
            ),
            {"user_id": user_id, "role_id": role_id},
        )


def downgrade() -> None:
    conn = op.get_bind()

    usernames = [user["username"] for user in TRIAL_USERS]
    conn.execute(
        sa.text(
            """
            DELETE FROM users
            WHERE username = ANY(:usernames)
            """
        ),
        {"usernames": usernames},
    )

    conn.execute(
        sa.text(
            """
            DELETE FROM roles
            WHERE name IN ('REQUESTER', 'PURCHASING', 'WAREHOUSE', 'FINANCE', 'MANAGER')
            """
        )
    )
