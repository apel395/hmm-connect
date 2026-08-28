"""Split Receiving permissions by business action.

Revision ID: 20260828_receiving_granular_permissions
Revises: 20260827_pr_approval_repair
"""

from alembic import op


revision = "20260828_receiving_granular_permissions"
down_revision = "20260827_pr_approval_repair"
branch_labels = None
depends_on = None


PERMISSIONS = (
    "receiving.create",
    "receiving.edit",
    "receiving.submit",
    "receiving.approve",
    "receiving.post",
    "receiving.return",
)

ROLE_GRANTS = {
    "STORE": (
        "receiving.view", "receiving.create", "receiving.edit",
        "receiving.submit", "receiving.approve", "receiving.post", "receiving.return",
    ),
    "WAREHOUSE": (
        "receiving.view", "receiving.create", "receiving.edit",
        "receiving.submit", "receiving.post", "receiving.return",
    ),
    "PURCHASING": (
        "receiving.view", "receiving.create", "receiving.edit",
        "receiving.submit", "receiving.post", "receiving.return",
    ),
    "CHEF": ("receiving.view", "receiving.edit", "receiving.approve"),
    "PM/CAMP BOSS": ("receiving.view", "receiving.edit", "receiving.approve"),
    "HO PURCHASING": ("receiving.view",),
    "FINANCE": ("receiving.view",),
    "GENERAL MANAGER": ("receiving.view",),
    "GENERAL_MANAGER": ("receiving.view",),
    "AUDITOR": ("receiving.view",),
}


def upgrade() -> None:
    for code in PERMISSIONS:
        label = code.replace(".", " ").replace("_", " ").title()
        op.execute(
            f"""
            INSERT INTO permissions (code, description)
            VALUES ('{code}', '{label}')
            ON CONFLICT (code) DO NOTHING
            """
        )

    # receiving.manage remains an administrator umbrella. Operational roles get
    # explicit permissions so Approve is never granted merely because a user can
    # create/edit/post Receiving documents.
    op.execute(
        """
        DELETE FROM role_permissions rp
        USING roles r, permissions p
        WHERE rp.role_id = r.id
          AND rp.permission_id = p.id
          AND p.code = 'receiving.manage'
          AND r.name <> 'SYSTEM_ADMINISTRATOR'
        """
    )

    values = []
    for role_name, permissions in ROLE_GRANTS.items():
        for permission_code in permissions:
            safe_role = role_name.replace("'", "''")
            safe_permission = permission_code.replace("'", "''")
            values.append(f"('{safe_role}', '{safe_permission}')")
    op.execute(
        f"""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM (VALUES {", ".join(values)}) AS grant_map(role_name, permission_code)
        JOIN roles r ON r.name = grant_map.role_name
        JOIN permissions p ON p.code = grant_map.permission_code
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    # Do not silently collapse live granular permissions back into receiving.manage.
    pass
