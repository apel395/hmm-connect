#!/usr/bin/env python3
"""One-time, guarded repair of six WH-005 stock averages after the 2025 purge.

Stock movement cost is authoritative only when every remaining movement is an
IN from a POSTED 2026 warehouse receipt and agrees with its receipt item.
The command previews by default. --apply changes average_cost in one transaction;
it never changes quantities, movements, receipts, or accounting journals.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.chart_of_account import ChartOfAccount
from app.models.goods_receipt import GoodsReceipt, GoodsReceiptItem
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.stock_movement import StockMovement
from app.models.warehouse import Warehouse

D = Decimal
CENT = D("0.01")
COST_PRECISION = D("0.0001")
WAREHOUSE_CODE = "WH-005"
ACCOUNT_CODE = "100-300-100"
EXPECTED_GAP = D("673574.35")


@dataclass(frozen=True)
class Target:
    code: str
    quantity: Decimal
    old_average: Decimal
    movement_value: Decimal
    movement_count: int


TARGETS = (
    Target("1-100004", D("243.1100"), D("138256.8818"), D("34184290.00"), 2),
    Target("1-100001", D("5.0000"), D("91137.0000"), D("524455.00"), 1),
    Target("1-800098", D("10.0000"), D("23500.0000"), D("250000.00"), 1),
    Target("1-800012", D("2.0000"), D("176400.0000"), D("363800.00"), 1),
    Target("1-200001", D("5.0000"), D("88563.2222"), D("448955.00"), 1),
    Target("1-100002", D("10.0000"), D("59068.4000"), D("590690.00"), 1),
)


class ChangedStock(RuntimeError):
    """Production data no longer matches the reviewed six-row snapshot."""


@dataclass(frozen=True)
class Change:
    inventory_id: int
    product_code: str
    quantity: Decimal
    old_average: Decimal
    new_average: Decimal
    before_value: Decimal
    movement_value: Decimal
    receipt_numbers: tuple[str, ...]


def build_plan(db: Session, *, lock: bool = False) -> list[tuple[Inventory, Change]]:
    query = (
        db.query(Inventory, Product, Warehouse, ChartOfAccount)
        .join(Product, Product.id == Inventory.product_id)
        .join(Warehouse, Warehouse.id == Inventory.warehouse_id)
        .join(ChartOfAccount, ChartOfAccount.id == Product.inventory_account_id)
        .filter(Product.code.in_([target.code for target in TARGETS]),
                Warehouse.code == WAREHOUSE_CODE)
        .order_by(Inventory.id)
    )
    if lock:
        # Receipt posting and stock adjustments also lock these Inventory rows.
        query = query.with_for_update(of=Inventory)
    rows = query.all()
    by_code = {product.code: (inventory, warehouse, account)
               for inventory, product, warehouse, account in rows}
    if len(rows) != len(TARGETS) or len(by_code) != len(TARGETS):
        raise ChangedStock("The six inventory rows are missing or duplicated")

    plan: list[tuple[Inventory, Change]] = []
    for target in TARGETS:
        inventory, warehouse, account = by_code[target.code]
        if warehouse.code != WAREHOUSE_CODE or account.account_number != ACCOUNT_CODE:
            raise ChangedStock(f"{target.code}: warehouse or inventory account changed")
        qty = D(inventory.quantity or 0)
        average = D(inventory.average_cost or 0)
        if qty != target.quantity or average != target.old_average:
            raise ChangedStock(
                f"{target.code}: stock snapshot changed: qty={qty} avg={average}"
            )

        movements = (
            db.query(StockMovement, GoodsReceipt, GoodsReceiptItem)
            .outerjoin(GoodsReceipt, GoodsReceipt.id == StockMovement.goods_receipt_id)
            .outerjoin(GoodsReceiptItem,
                       GoodsReceiptItem.id == StockMovement.goods_receipt_item_id)
            .filter(StockMovement.product_id == inventory.product_id,
                    StockMovement.warehouse_id == inventory.warehouse_id)
            .order_by(StockMovement.id)
            .all()
        )
        if len(movements) != target.movement_count:
            raise ChangedStock(f"{target.code}: movement count changed")

        movement_qty = D("0")
        movement_value = D("0")
        receipts = []
        for movement, receipt, item in movements:
            if (movement.movement_type != "IN"
                    or movement.reference_type != "GOODS_RECEIPT"
                    or receipt is None or item is None
                    or receipt.status != "POSTED"
                    or receipt.destination_type != "WAREHOUSE"
                    or receipt.warehouse_id != inventory.warehouse_id
                    or receipt.received_at.date() < date(2026, 1, 1)
                    or item.goods_receipt_id != receipt.id
                    or item.product_id != inventory.product_id
                    or D(item.quantity) != D(movement.quantity)
                    or D(item.unit_cost) != D(movement.unit_cost)
                    or (movement.inventory_account_id is not None
                        and movement.inventory_account_id != account.id)):
                raise ChangedStock(
                    f"{target.code}: movement {movement.id} is not a matching "
                    "posted 2026 receipt line"
                )
            movement_qty += D(movement.quantity)
            movement_value += D(movement.quantity) * D(movement.unit_cost)
            receipts.append(receipt.receipt_number)

        if movement_qty != qty or movement_value != target.movement_value:
            raise ChangedStock(
                f"{target.code}: remaining movement qty/value changed: "
                f"{movement_qty} / {movement_value}"
            )
        new_average = (movement_value / qty).quantize(
            COST_PRECISION, rounding=ROUND_HALF_UP
        )
        if (qty * new_average - movement_value).quantize(
            CENT, rounding=ROUND_HALF_UP
        ) != 0:
            raise ChangedStock(f"{target.code}: four-decimal average cannot match cents")
        plan.append((inventory, Change(
            inventory_id=inventory.id, product_code=target.code,
            quantity=qty, old_average=average, new_average=new_average,
            before_value=qty * average, movement_value=movement_value,
            receipt_numbers=tuple(receipts),
        )))

    gap = sum((change.movement_value - change.before_value
               for _, change in plan), D("0"))
    if gap.quantize(CENT, rounding=ROUND_HALF_UP) != EXPECTED_GAP:
        raise ChangedStock(f"Total gap changed: {gap}")
    return plan


def execute(db: Session, *, apply: bool = False) -> list[Change]:
    try:
        plan = build_plan(db, lock=apply)
        changes = [change for _, change in plan]
        if apply:
            for inventory, change in plan:
                inventory.average_cost = change.new_average
            db.flush()
            for inventory, change in plan:
                if (D(inventory.quantity) * D(inventory.average_cost)
                        - change.movement_value).quantize(
                            CENT, rounding=ROUND_HALF_UP
                        ) != 0:
                    raise ChangedStock(f"{change.product_code}: post-update check failed")
            db.commit()
        else:
            db.rollback()
        return changes
    except Exception:
        db.rollback()
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Commit the guarded six-row correction")
    args = parser.parse_args()
    with SessionLocal() as db:
        try:
            changes = execute(db, apply=args.apply)
        except ChangedStock as exc:
            print(f"REFUSED: {exc}", file=sys.stderr)
            return 2
    for change in changes:
        print(
            change.product_code, f"inventory_id={change.inventory_id}",
            f"qty={change.quantity}",
            f"average={change.old_average} -> {change.new_average}",
            f"value={change.before_value:.2f} -> "
            f"{change.quantity * change.new_average:.2f}",
            f"receipts={','.join(change.receipt_numbers)}",
        )
    print("COMMITTED" if args.apply else "DRY RUN: no changes made")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
