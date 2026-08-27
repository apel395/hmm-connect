#!/usr/bin/env python3
"""Audit Purchase Requisition approval snapshots.

Usage:
  PYTHONPATH=. python scripts/audit_pr_approvals.py
"""

from app.core.database import SessionLocal
from app.models.approval_request import ApprovalRequest
from app.models.purchase_requisition import PurchaseRequisition

EXPECTED = ["STORE", "CHEF", "PM/CAMP BOSS"]


def main() -> int:
    db = SessionLocal()
    try:
        rows = db.query(PurchaseRequisition).order_by(PurchaseRequisition.id).all()
        print("=== PURCHASE REQUISITION APPROVAL AUDIT ===")
        invalid = 0
        for pr in rows:
            request = (
                db.query(ApprovalRequest)
                .filter(
                    ApprovalRequest.entity_type == "PURCHASE_REQUISITION",
                    ApprovalRequest.entity_id == pr.id,
                )
                .order_by(ApprovalRequest.id.desc())
                .first()
            )
            if not request:
                print(
                    f"PR id={pr.id} {pr.pr_number} status={pr.status} "
                    f"location={pr.location.name if pr.location else '—'} approval=NONE"
                )
                continue
            steps = sorted(request.steps, key=lambda row: row.step_order)
            roles = [step.approver_role_name for step in steps]
            chain_ok = roles == EXPECTED
            if not chain_ok:
                invalid += 1
            step_text = " -> ".join(
                f"{step.approver_role_name}[{step.status}]"
                for step in steps
            )
            print(
                f"[{'OK' if chain_ok else 'INVALID'}] PR id={pr.id} {pr.pr_number} "
                f"status={pr.status} location={pr.location.name if pr.location else '—'} "
                f"request_status={request.status} current_step={request.current_step_order} | {step_text}"
            )
        print(f"\nAudit summary: total_pr={len(rows)}, invalid_approval_chains={invalid}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
