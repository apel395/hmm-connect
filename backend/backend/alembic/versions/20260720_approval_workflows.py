"""add configurable layered approval workflows

Revision ID: 20260720_approval_workflows
Revises: 20260720_hmm_connect
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260720_approval_workflows"
down_revision: Union[str, Sequence[str], None] = "20260720_hmm_connect"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "approval_workflows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("code", name="uq_approval_workflows_code"),
    )
    op.create_index("ix_approval_workflows_code", "approval_workflows", ["code"])

    op.create_table(
        "approval_workflow_steps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workflow_id", sa.Integer(), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("approver_role_id", sa.Integer(), nullable=False),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("location_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workflow_id"], ["approval_workflows.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["approver_role_id"], ["roles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("workflow_id", "step_order", name="uq_approval_workflow_step_order"),
    )
    op.create_index("ix_approval_workflow_steps_workflow_id", "approval_workflow_steps", ["workflow_id"])

    op.create_table(
        "approval_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workflow_id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="PENDING"),
        sa.Column("current_step_order", sa.Integer(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["workflow_id"], ["approval_workflows.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("entity_type", "entity_id", name="uq_approval_request_entity"),
    )
    op.create_index("ix_approval_requests_entity_type", "approval_requests", ["entity_type"])
    op.create_index("ix_approval_requests_entity_id", "approval_requests", ["entity_id"])

    op.create_table(
        "approval_request_steps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("approval_request_id", sa.Integer(), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("approver_role_name", sa.String(50), nullable=False),
        sa.Column("department_name", sa.String(100), nullable=True),
        sa.Column("location_name", sa.String(120), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="WAITING"),
        sa.Column("approved_by_id", sa.Integer(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_comment", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["approval_request_id"], ["approval_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["approved_by_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_approval_request_steps_approval_request_id", "approval_request_steps", ["approval_request_id"])

    conn = op.get_bind()

    conn.execute(
        sa.text(
            """
            INSERT INTO roles (name, description)
            VALUES ('SECTION_APPROVER', 'Approve documents at section level')
            ON CONFLICT (name) DO NOTHING
            """
        )
    )

    conn.execute(
        sa.text(
            """
            INSERT INTO approval_workflows (code, name, entity_type)
            VALUES
                ('PR_APPROVAL', 'Purchase Requisition Approval', 'PURCHASE_REQUISITION'),
                ('PO_APPROVAL', 'Purchase Order Approval', 'PURCHASE_ORDER')
            ON CONFLICT (code) DO NOTHING
            """
        )
    )

    conn.execute(
        sa.text(
            """
            INSERT INTO users
                (username, email, full_name, password_hash, is_active, department_id, location_id)
            SELECT
                'section',
                'section@example.com',
                'Trial Section Approver',
                '$2y$12$pC./LNuPeq8xKKcMRWsxq.yLferMbGI1CQZK8GJe7yAIsBhHP6XKO',
                true,
                d.id,
                l.id
            FROM departments d
            CROSS JOIN locations l
            WHERE d.code = 'OPERATIONS'
              AND l.code = 'JKT'
              AND NOT EXISTS (
                  SELECT 1 FROM users WHERE username = 'section'
              )
            """
        )
    )

    conn.execute(
        sa.text(
            """
            INSERT INTO user_roles (user_id, role_id)
            SELECT u.id, r.id
            FROM users u
            CROSS JOIN roles r
            WHERE u.username = 'section'
              AND r.name = 'SECTION_APPROVER'
              AND NOT EXISTS (
                  SELECT 1
                  FROM user_roles ur
                  WHERE ur.user_id = u.id
                    AND ur.role_id = r.id
              )
            """
        )
    )

    conn.execute(
        sa.text(
            """
            INSERT INTO approval_workflow_steps
                (workflow_id, step_order, name, approver_role_id)
            SELECT w.id, steps.step_order, steps.name, r.id
            FROM (
                VALUES
                    ('PR_APPROVAL', 1, 'Section Approval', 'SECTION_APPROVER'),
                    ('PR_APPROVAL', 2, 'Manager Approval', 'MANAGER'),
                    ('PO_APPROVAL', 1, 'Section Approval', 'SECTION_APPROVER'),
                    ('PO_APPROVAL', 2, 'Manager Approval', 'MANAGER'),
                    ('PO_APPROVAL', 3, 'Finance Approval', 'FINANCE')
            ) AS steps(workflow_code, step_order, name, role_name)
            JOIN approval_workflows w ON w.code = steps.workflow_code
            JOIN roles r ON r.name = steps.role_name
            ON CONFLICT (workflow_id, step_order) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_approval_request_steps_approval_request_id", table_name="approval_request_steps")
    op.drop_table("approval_request_steps")
    op.drop_index("ix_approval_requests_entity_id", table_name="approval_requests")
    op.drop_index("ix_approval_requests_entity_type", table_name="approval_requests")
    op.drop_table("approval_requests")
    op.drop_constraint("uq_approval_workflow_step_order", "approval_workflow_steps", type_="unique")
    op.drop_index("ix_approval_workflow_steps_workflow_id", table_name="approval_workflow_steps")
    op.drop_table("approval_workflow_steps")
    op.drop_index("ix_approval_workflows_code", table_name="approval_workflows")
    op.drop_table("approval_workflows")
