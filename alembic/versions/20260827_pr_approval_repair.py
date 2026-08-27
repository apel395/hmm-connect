"""Repair PR approval snapshots and allow Purchasing PR creation.

Revision ID: 20260827_pr_approval_repair
Revises: 20260827_finance_posting_scope_integrity
"""

from alembic import op


revision = "20260827_pr_approval_repair"
down_revision = "20260827_finance_posting_scope_integrity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ensure the PR master workflow is exactly Store -> Chef -> PM/Camp Boss.
    op.execute(
        """
        DO $$
        DECLARE
            wf_id integer;
            store_id integer;
            chef_id integer;
            pm_id integer;
        BEGIN
            SELECT id INTO store_id FROM roles WHERE upper(name) = 'STORE' LIMIT 1;
            SELECT id INTO chef_id FROM roles WHERE upper(name) = 'CHEF' LIMIT 1;
            SELECT id INTO pm_id FROM roles
            WHERE upper(regexp_replace(name, '[^A-Z0-9]+', '_', 'g')) = 'PM_CAMP_BOSS'
            LIMIT 1;

            IF store_id IS NULL OR chef_id IS NULL OR pm_id IS NULL THEN
                RAISE EXCEPTION 'Required PR approval roles STORE/CHEF/PM-CAMP BOSS are missing';
            END IF;

            SELECT id INTO wf_id FROM approval_workflows WHERE code = 'PR_APPROVAL' LIMIT 1;
            IF wf_id IS NULL THEN
                INSERT INTO approval_workflows (code, name, entity_type, is_active, created_at, updated_at)
                VALUES ('PR_APPROVAL', 'Purchase Requisition Approval', 'PURCHASE_REQUISITION', true, now(), now())
                RETURNING id INTO wf_id;
            ELSE
                UPDATE approval_workflows
                SET name = 'Purchase Requisition Approval',
                    entity_type = 'PURCHASE_REQUISITION',
                    is_active = true,
                    updated_at = now()
                WHERE id = wf_id;
            END IF;

            DELETE FROM approval_workflow_steps WHERE workflow_id = wf_id;

            INSERT INTO approval_workflow_steps
                (workflow_id, step_order, name, approver_role_id, department_id, location_id, created_at, updated_at)
            VALUES
                (wf_id, 1, 'Store Approval', store_id, NULL, NULL, now(), now()),
                (wf_id, 2, 'Chef Approval', chef_id, NULL, NULL, now(), now()),
                (wf_id, 3, 'PM / Camp Boss Approval', pm_id, NULL, NULL, now(), now());
        END $$;
        """
    )

    # Existing PENDING PR approval requests are immutable snapshots. Repair only
    # snapshots that are not already the correct three-role chain. Any approval
    # made against an invalid legacy/admin chain is intentionally discarded and
    # the document restarts at Store.
    op.execute(
        """
        DO $$
        DECLARE
            req record;
            loc_name text;
            wf_id integer;
        BEGIN
            SELECT id INTO wf_id FROM approval_workflows WHERE code = 'PR_APPROVAL' LIMIT 1;

            FOR req IN
                SELECT ar.id, ar.entity_id
                FROM approval_requests ar
                WHERE ar.entity_type = 'PURCHASE_REQUISITION'
                  AND ar.status = 'PENDING'
                  AND (
                      (SELECT count(*) FROM approval_request_steps s
                       WHERE s.approval_request_id = ar.id) <> 3
                      OR EXISTS (
                          SELECT 1
                          FROM approval_request_steps s
                          WHERE s.approval_request_id = ar.id
                            AND upper(regexp_replace(s.approver_role_name, '[^A-Z0-9]+', '_', 'g'))
                                NOT IN ('STORE', 'CHEF', 'PM_CAMP_BOSS')
                      )
                  )
            LOOP
                SELECT l.name INTO loc_name
                FROM purchase_requisitions pr
                LEFT JOIN locations l ON l.id = pr.location_id
                WHERE pr.id = req.entity_id;

                DELETE FROM approval_request_steps
                WHERE approval_request_id = req.id;

                INSERT INTO approval_request_steps
                    (approval_request_id, step_order, name, approver_role_name,
                     department_name, location_name, status,
                     approved_by_id, decided_at, decision_comment)
                VALUES
                    (req.id, 1, 'Store Approval', 'STORE', NULL, loc_name, 'PENDING', NULL, NULL, NULL),
                    (req.id, 2, 'Chef Approval', 'CHEF', NULL, loc_name, 'WAITING', NULL, NULL, NULL),
                    (req.id, 3, 'PM / Camp Boss Approval', 'PM/CAMP BOSS', NULL, loc_name, 'WAITING', NULL, NULL, NULL);

                UPDATE approval_requests
                SET workflow_id = wf_id,
                    current_step_order = 1,
                    completed_at = NULL
                WHERE id = req.id;

                UPDATE purchase_requisitions
                SET status = 'PENDING_APPROVAL'
                WHERE id = req.entity_id;
            END LOOP;
        END $$;
        """
    )

    # Purchasing may create/edit/submit PRs, but PR approval remains exclusively
    # controlled by the Store -> Chef -> PM/Camp Boss workflow.
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        JOIN permissions p ON p.code IN ('pr.create', 'pr.edit', 'pr.submit')
        WHERE r.name = 'PURCHASING'
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    # Do not restore invalid legacy approval snapshots or silently remove live
    # permissions from administrator-managed production roles.
    pass
