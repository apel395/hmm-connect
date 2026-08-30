#!/usr/bin/env python3
"""Read-only inventory integrity audit.

Reports:
- POSTED warehouse receipts without one IN stock movement per receipt line
- POSTED warehouse receipts whose inventory balance row is missing
- Stock Opname documents with zero items or warehouse/location mismatch
- Store Requests with zero items or warehouse/location mismatch
- Store Issues with zero items

No data is changed.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.database import SessionLocal
from app.models.goods_receipt import GoodsReceipt
from app.models.inventory import Inventory
from app.models.stock_movement import StockMovement
from app.models.stock_opname import StockOpname
from app.models.store_request import StoreIssue, StoreRequest


def main() -> int:
    db = SessionLocal()
    try:
        issues = 0

        receipts = (
            db.query(GoodsReceipt)
            .filter(
                GoodsReceipt.status == "POSTED",
                GoodsReceipt.destination_type == "WAREHOUSE",
            )
            .order_by(GoodsReceipt.id)
            .all()
        )
        for receipt in receipts:
            movement_count = (
                db.query(StockMovement)
                .filter(
                    StockMovement.goods_receipt_id == receipt.id,
                    StockMovement.reference_type == "GOODS_RECEIPT",
                    StockMovement.movement_type == "IN",
                )
                .count()
            )
            if movement_count != len(receipt.items):
                issues += 1
                print(
                    "RECEIPT_MOVEMENT_MISMATCH",
                    receipt.receipt_number,
                    f"items={len(receipt.items)}",
                    f"movements={movement_count}",
                    f"warehouse_id={receipt.warehouse_id}",
                    f"location_id={receipt.location_id}",
                )
            for item in receipt.items:
                inventory = (
                    db.query(Inventory)
                    .filter(
                        Inventory.product_id == item.product_id,
                        Inventory.warehouse_id == receipt.warehouse_id,
                    )
                    .first()
                )
                if inventory is None:
                    issues += 1
                    print(
                        "RECEIPT_MISSING_INVENTORY",
                        receipt.receipt_number,
                        f"item_id={item.id}",
                        f"product_id={item.product_id}",
                        f"warehouse_id={receipt.warehouse_id}",
                    )

        for opname in db.query(StockOpname).order_by(StockOpname.id).all():
            if not opname.items:
                issues += 1
                print(
                    "EMPTY_STOCK_OPNAME",
                    opname.opname_number,
                    opname.status,
                    f"warehouse_id={opname.warehouse_id}",
                    f"location_id={opname.location_id}",
                )
            if opname.warehouse and opname.warehouse.location_id != opname.location_id:
                issues += 1
                print(
                    "STOCK_OPNAME_SCOPE_MISMATCH",
                    opname.opname_number,
                    f"warehouse_location_id={opname.warehouse.location_id}",
                    f"document_location_id={opname.location_id}",
                )

        for request in db.query(StoreRequest).order_by(StoreRequest.id).all():
            if not request.items:
                issues += 1
                print(
                    "EMPTY_STORE_REQUEST",
                    request.sr_number,
                    request.status,
                    f"warehouse_id={request.warehouse_id}",
                    f"location_id={request.location_id}",
                )
            if request.warehouse and request.warehouse.location_id != request.location_id:
                issues += 1
                print(
                    "STORE_REQUEST_SCOPE_MISMATCH",
                    request.sr_number,
                    f"warehouse_location_id={request.warehouse.location_id}",
                    f"document_location_id={request.location_id}",
                )

        for issue in db.query(StoreIssue).order_by(StoreIssue.id).all():
            if not issue.items:
                issues += 1
                print(
                    "EMPTY_STORE_ISSUE",
                    issue.issue_number,
                    issue.status,
                    f"store_request_id={issue.store_request_id}",
                )

        print(f"inventory_integrity_issues={issues}")
        return 1 if issues else 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
