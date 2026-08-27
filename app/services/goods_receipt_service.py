from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.dependencies.authorization import has_permission
from app.models.goods_receipt import GoodsReceipt, GoodsReceiptItem
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.stock_movement import StockMovement
from app.models.supplier import Supplier
from app.models.supplier_invoice import SupplierInvoice
from app.models.warehouse import Warehouse
from app.schemas.goods_receipt import GoodsReceiptCostCorrection, GoodsReceiptCreate
from app.services.activity_service import ActivityService
from app.services.document_number import next_document_number

ZERO = Decimal("0")
MONEY = Decimal("0.01")


class GoodsReceiptService:
    @staticmethod
    def _number(db: Session) -> str:
        return next_document_number(db, "GR", digits=5, day=True)

    @staticmethod
    def _check_access(user, *_legacy_roles):
        if not has_permission(user, "receiving.manage"):
            raise HTTPException(status_code=403, detail="Receiving manage permission required")

    @staticmethod
    def can_correct_cost(user) -> bool:
        return has_permission(user, "receiving.manage")

    @staticmethod
    def _validate_destination(db: Session, data: GoodsReceiptCreate, location_id: int | None):
        if data.destination_type == "WAREHOUSE":
            if data.warehouse_id is None:
                raise HTTPException(status_code=400, detail="Warehouse is required for warehouse receiving")
            warehouse = db.get(Warehouse, data.warehouse_id)
            if not warehouse:
                raise HTTPException(status_code=404, detail="Warehouse not found")
            if location_id is None:
                raise HTTPException(status_code=409, detail="Receiving location is required for warehouse validation")
            if warehouse.location_id is None:
                raise HTTPException(status_code=409, detail="Warehouse must be assigned to a work location before receiving")
            if warehouse.location_id != location_id:
                raise HTTPException(status_code=409, detail="Warehouse must belong to the receiving work location")

    @staticmethod
    def _po_dimensions(purchase_order: PurchaseOrder):
        """Return canonical PO dimensions, repairing only uniquely resolvable legacy gaps."""
        sources = list(purchase_order.source_purchase_requisitions)
        if purchase_order.market_list is not None:
            sources.append(purchase_order.market_list)

        resolved = {}
        for field in ("business_unit_id", "location_id", "department_id"):
            current = getattr(purchase_order, field)
            if current is not None:
                resolved[field] = current
                continue
            values = {getattr(source, field) for source in sources if getattr(source, field) is not None}
            if len(values) > 1:
                label = field.removesuffix("_id").replace("_", " ")
                raise HTTPException(
                    status_code=409,
                    detail=f"Purchase order sources contain conflicting {label} values",
                )
            resolved[field] = next(iter(values), None)
            if resolved[field] is not None:
                setattr(purchase_order, field, resolved[field])
        return resolved["business_unit_id"], resolved["location_id"], resolved["department_id"]

    @staticmethod
    def _inventory_for_update(db: Session, product_id: int, warehouse_id: int) -> Inventory:
        inventory = (
            db.query(Inventory)
            .filter(
                Inventory.product_id == product_id,
                Inventory.warehouse_id == warehouse_id,
            )
            .with_for_update()
            .first()
        )
        if inventory:
            return inventory

        if db.get_bind().dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert

            db.execute(
                insert(Inventory)
                .values(
                    product_id=product_id,
                    warehouse_id=warehouse_id,
                    quantity=ZERO,
                    average_cost=ZERO,
                )
                .on_conflict_do_nothing(
                    index_elements=[Inventory.product_id, Inventory.warehouse_id]
                )
            )
            db.flush()
            return (
                db.query(Inventory)
                .filter(
                    Inventory.product_id == product_id,
                    Inventory.warehouse_id == warehouse_id,
                )
                .with_for_update()
                .one()
            )

        inventory = Inventory(
            product_id=product_id,
            warehouse_id=warehouse_id,
            quantity=ZERO,
            average_cost=ZERO,
        )
        db.add(inventory)
        db.flush()
        return inventory

    @staticmethod
    def _movement(receipt: GoodsReceipt, receipt_item: GoodsReceiptItem, movement_type: str, reference_type: str):
        return StockMovement(
            product_id=receipt_item.product_id, warehouse_id=receipt.warehouse_id,
            goods_receipt_id=receipt.id, goods_receipt_item_id=receipt_item.id,
            purchase_order_id=receipt.purchase_order_id, purchase_order_item_id=receipt_item.purchase_order_item_id,
            business_unit_id=receipt.business_unit_id, location_id=receipt.location_id, department_id=receipt.department_id,
            movement_type=movement_type, quantity=receipt_item.quantity, unit_cost=receipt_item.unit_cost,
            reference_type=reference_type, reference_id=receipt.id,
        )

    @staticmethod
    def _tax_amount(quantity: Decimal, unit_cost: Decimal, is_taxable: bool, tax_rate: Decimal) -> Decimal:
        if not is_taxable or tax_rate <= 0:
            return ZERO
        return (quantity * unit_cost * tax_rate / Decimal("100")).quantize(MONEY, rounding=ROUND_HALF_UP)

    @classmethod
    def _recalculate_totals(cls, receipt: GoodsReceipt) -> None:
        subtotal = ZERO
        tax = ZERO
        for item in receipt.items:
            line_subtotal = Decimal(item.quantity or 0) * Decimal(item.unit_cost or 0)
            item.tax_amount = cls._tax_amount(
                Decimal(item.quantity or 0), Decimal(item.unit_cost or 0), bool(item.is_taxable), Decimal(item.tax_rate or 0)
            )
            subtotal += line_subtotal
            tax += Decimal(item.tax_amount or 0)
        receipt.subtotal = subtotal.quantize(MONEY, rounding=ROUND_HALF_UP)
        receipt.tax_amount = tax.quantize(MONEY, rounding=ROUND_HALF_UP)
        receipt.total_amount = (receipt.subtotal + receipt.tax_amount).quantize(MONEY, rounding=ROUND_HALF_UP)

    @classmethod
    def create(cls, db: Session, *, data: GoodsReceiptCreate, user):
        cls._check_access(user, "WAREHOUSE", "PURCHASING")
        from app.services.organization_dimensions import validate_dimensions

        purchase_order = db.get(PurchaseOrder, data.purchase_order_id) if data.purchase_order_id else None
        if data.purchase_order_id:
            if not purchase_order:
                raise HTTPException(status_code=404, detail="Purchase order not found")
            if purchase_order.status not in {"APPROVED", "PARTIALLY_RECEIVED"}:
                raise HTTPException(status_code=409, detail="Only approved purchase orders can be received")
            business_unit_id, location_id, department_id = cls._po_dimensions(purchase_order)
            supplier_id = purchase_order.supplier_id
        else:
            supplier = db.get(Supplier, data.supplier_id)
            if not supplier or not supplier.is_active:
                raise HTTPException(status_code=404, detail="Active supplier not found")
            business_unit_id, location_id, department_id, supplier_id = data.business_unit_id, data.location_id, data.department_id, data.supplier_id

        validate_dimensions(db, business_unit_id, location_id, department_id, True)
        cls._validate_destination(db, data, location_id)
        receipt = GoodsReceipt(
            receipt_number=cls._number(db), status="DRAFT", purchase_order_id=purchase_order.id if purchase_order else None,
            supplier_id=supplier_id, received_by_id=user.id, received_at=data.received_at or datetime.now(timezone.utc),
            source_type=data.source_type, external_reference=data.external_reference, receipt_type=data.receipt_type,
            destination_type=data.destination_type, warehouse_id=data.warehouse_id if data.destination_type == "WAREHOUSE" else None,
            notes=data.notes, business_unit_id=business_unit_id, location_id=location_id, department_id=department_id,
        )

        seen = set()
        cost_overrides = []
        for incoming in data.items:
            if purchase_order:
                if incoming.purchase_order_item_id in seen:
                    raise HTTPException(status_code=400, detail="A PO item may appear only once per receipt")
                seen.add(incoming.purchase_order_item_id)
                po_item = db.get(PurchaseOrderItem, incoming.purchase_order_item_id)
                if not po_item or po_item.purchase_order_id != purchase_order.id:
                    raise HTTPException(status_code=400, detail="Receipt item does not belong to the purchase order")
                remaining = Decimal(po_item.quantity) - Decimal(po_item.received_quantity or 0)
                if remaining <= 0 or Decimal(incoming.quantity) > remaining:
                    raise HTTPException(status_code=409, detail=f"Quantity exceeds remaining amount for PO item {po_item.id}")
                po_cost = Decimal(po_item.unit_price or 0)
                unit_cost = Decimal(incoming.unit_cost) if incoming.unit_cost is not None else po_cost
                if incoming.unit_cost is not None and unit_cost != po_cost:
                    if not cls.can_correct_cost(user):
                        raise HTTPException(status_code=403, detail="Only an authorized manager can override PO cost during receiving")
                    if not (data.cost_correction_reason or "").strip():
                        raise HTTPException(status_code=400, detail="Correction reason is required when receiving cost differs from the PO")
                    cost_overrides.append({"purchase_order_item_id": po_item.id, "product_id": po_item.product_id, "po_unit_cost": str(po_cost), "receiving_unit_cost": str(unit_cost)})
                if unit_cost <= 0:
                    raise HTTPException(status_code=409, detail=f"Receiving unit cost must be greater than zero for PO item {po_item.id}")
                receipt.items.append(GoodsReceiptItem(
                    purchase_order_item_id=po_item.id, product_id=po_item.product_id, quantity=incoming.quantity, unit_cost=unit_cost,
                    is_taxable=bool(po_item.is_taxable), tax_rate=Decimal(po_item.tax_rate or 0),
                ))
            else:
                if incoming.product_id in seen:
                    raise HTTPException(status_code=400, detail="A product may appear only once per direct receipt")
                seen.add(incoming.product_id)
                product = db.get(Product, incoming.product_id)
                if not product:
                    raise HTTPException(status_code=404, detail=f"Product {incoming.product_id} not found")
                if str(product.tax_category or "REVIEW_REQUIRED").upper() == "REVIEW_REQUIRED":
                    raise HTTPException(status_code=409, detail=f"Product {product.code} requires Finance tax review before receiving")
                unit_cost = Decimal(incoming.unit_cost or 0)
                if unit_cost <= 0:
                    raise HTTPException(status_code=409, detail=f"Receiving unit cost must be greater than zero for product {product.id}")
                receipt.items.append(GoodsReceiptItem(
                    purchase_order_item_id=None, product_id=product.id, quantity=incoming.quantity, unit_cost=unit_cost,
                    is_taxable=bool(product.is_taxable), tax_rate=Decimal(product.tax_rate or 0),
                ))

        cls._recalculate_totals(receipt)
        db.add(receipt)
        db.flush()
        ActivityService.log(
            db=db, user=user, action="CREATE", entity_type="GOODS_RECEIPT", entity_id=receipt.id,
            summary=f"Created {receipt.receipt_number}", document_type="GR", document_number=receipt.receipt_number,
            document_status="DRAFT", reference_document=purchase_order.po_number if purchase_order else "DIRECT_RECEIPT",
            details={"source": "PO" if purchase_order else "DIRECT", "cost_overrides": cost_overrides, "subtotal": str(receipt.subtotal), "tax_amount": str(receipt.tax_amount), "total_amount": str(receipt.total_amount)},
        )
        db.commit(); db.refresh(receipt); return receipt

    @classmethod
    def post(cls, db: Session, *, receipt_id: int, user):
        cls._check_access(user, "WAREHOUSE", "PURCHASING")
        receipt = db.query(GoodsReceipt).filter(GoodsReceipt.id == receipt_id).with_for_update().first()
        if not receipt: raise HTTPException(status_code=404, detail="Goods receipt not found")
        if receipt.status != "DRAFT": raise HTTPException(status_code=409, detail="Only draft receipts can be posted")
        purchase_order = db.query(PurchaseOrder).filter(PurchaseOrder.id == receipt.purchase_order_id).with_for_update().first() if receipt.purchase_order_id else None
        if receipt.purchase_order_id and (not purchase_order or purchase_order.status not in {"APPROVED", "PARTIALLY_RECEIVED"}):
            raise HTTPException(status_code=409, detail="Purchase order is no longer receivable")
        if receipt.destination_type == "WAREHOUSE":
            warehouse = db.get(Warehouse, receipt.warehouse_id)
            if not warehouse or warehouse.location_id is None:
                raise HTTPException(status_code=409, detail="Receiving warehouse must be assigned to a work location")
            if warehouse.location_id != receipt.location_id:
                raise HTTPException(status_code=409, detail="Warehouse must belong to the receiving work location")
        cls._recalculate_totals(receipt)
        if Decimal(receipt.total_amount or 0) <= 0:
            raise HTTPException(status_code=409, detail="Goods receipt total must be greater than zero")
        for receipt_item in receipt.items:
            quantity = Decimal(receipt_item.quantity)
            if quantity <= 0: raise HTTPException(status_code=409, detail=f"Receipt item {receipt_item.id} must have positive quantity")
            if Decimal(receipt_item.unit_cost or 0) <= 0: raise HTTPException(status_code=409, detail=f"Receipt item {receipt_item.id} has zero unit cost and cannot be posted")
            if purchase_order:
                po_item = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.id == receipt_item.purchase_order_item_id, PurchaseOrderItem.purchase_order_id == purchase_order.id).with_for_update().first()
                if not po_item: raise HTTPException(status_code=409, detail=f"PO item for receipt line {receipt_item.id} no longer exists")
                remaining = Decimal(po_item.quantity) - Decimal(po_item.received_quantity or 0)
                if quantity > remaining: raise HTTPException(status_code=409, detail=f"Quantity exceeds remaining amount for PO item {po_item.id}")
                po_item.received_quantity = Decimal(po_item.received_quantity or 0) + quantity
                receipt_item.product_id = po_item.product_id
            if receipt.destination_type == "WAREHOUSE":
                inventory = cls._inventory_for_update(
                    db,
                    receipt_item.product_id,
                    receipt.warehouse_id,
                )
                old_qty, old_avg = Decimal(inventory.quantity or 0), Decimal(inventory.average_cost or 0)
                new_qty = old_qty + quantity
                inventory.average_cost = ((old_qty * old_avg) + (quantity * Decimal(receipt_item.unit_cost))) / new_qty
                inventory.quantity = new_qty
                db.add(cls._movement(receipt, receipt_item, "IN", "GOODS_RECEIPT"))
        if purchase_order:
            purchase_order.status = "RECEIVED" if all(Decimal(item.received_quantity or 0) >= Decimal(item.quantity) for item in purchase_order.items) else "PARTIALLY_RECEIVED"
        receipt.status = "POSTED"
        ActivityService.log(db=db, user=user, action="POST", entity_type="GOODS_RECEIPT", entity_id=receipt.id, summary=f"Posted {receipt.receipt_number}", document_type="GR", document_number=receipt.receipt_number, document_status="POSTED", reference_document=purchase_order.po_number if purchase_order else "DIRECT_RECEIPT", details={"purchase_order_id": receipt.purchase_order_id, "warehouse_id": receipt.warehouse_id, "destination_type": receipt.destination_type})
        db.commit(); db.refresh(receipt); return receipt

    @classmethod
    def correct_costs(cls, db: Session, *, receipt_id: int, data: GoodsReceiptCostCorrection, user):
        if not cls.can_correct_cost(user): raise HTTPException(status_code=403, detail="Only an authorized manager can correct receiving costs")
        receipt = db.query(GoodsReceipt).filter(GoodsReceipt.id == receipt_id).with_for_update().first()
        if not receipt: raise HTTPException(status_code=404, detail="Goods receipt not found")
        if receipt.status not in {"DRAFT", "POSTED"}: raise HTTPException(status_code=409, detail="Only draft or posted receipts can have their costs corrected")
        downstream_invoice = db.query(SupplierInvoice).filter(SupplierInvoice.goods_receipt_id == receipt.id, SupplierInvoice.status != "VOID").first()
        if downstream_invoice: raise HTTPException(status_code=409, detail=f"Receiving cost cannot be corrected after supplier invoice {downstream_invoice.internal_invoice_number} has been created")
        by_id = {item.id: item for item in receipt.items}; changes = []
        for correction in data.items:
            item = by_id.get(correction.item_id)
            if not item: raise HTTPException(status_code=400, detail=f"Receipt item {correction.item_id} does not belong to this receipt")
            old_cost, new_cost = Decimal(item.unit_cost or 0), Decimal(correction.unit_cost)
            if new_cost == old_cost: continue
            if receipt.status == "POSTED" and receipt.destination_type == "WAREHOUSE":
                movement = db.query(StockMovement).filter(StockMovement.goods_receipt_item_id == item.id, StockMovement.movement_type == "IN", StockMovement.reference_type == "GOODS_RECEIPT").order_by(StockMovement.id.asc()).first()
                if not movement: raise HTTPException(status_code=409, detail=f"Original inventory movement for receipt item {item.id} was not found")
                later_outbound = db.query(StockMovement).filter(StockMovement.product_id == item.product_id, StockMovement.warehouse_id == receipt.warehouse_id, StockMovement.id > movement.id, StockMovement.movement_type == "OUT").first()
                if later_outbound: raise HTTPException(status_code=409, detail=f"Cost for product {item.product_id} cannot be corrected after stock has moved out")
                inventory = db.query(Inventory).filter(Inventory.product_id == item.product_id, Inventory.warehouse_id == receipt.warehouse_id).with_for_update().first()
                if not inventory or Decimal(inventory.quantity or 0) <= 0: raise HTTPException(status_code=409, detail=f"Current inventory for product {item.product_id} cannot be revalued")
                qty, current_qty = Decimal(item.quantity), Decimal(inventory.quantity)
                inventory.average_cost = Decimal(inventory.average_cost or 0) + (((new_cost - old_cost) * qty) / current_qty)
                movement.unit_cost = new_cost
            item.unit_cost = new_cost
            changes.append({"item_id": item.id, "product_id": item.product_id, "old_unit_cost": str(old_cost), "new_unit_cost": str(new_cost)})
        if not changes: raise HTTPException(status_code=400, detail="No receiving costs changed")
        cls._recalculate_totals(receipt)
        ActivityService.log(db=db, user=user, action="COST_CORRECTION", entity_type="GOODS_RECEIPT", entity_id=receipt.id, summary=f"Corrected receiving cost for {receipt.receipt_number}", document_type="GR", document_number=receipt.receipt_number, document_status=receipt.status, reference_document=receipt.purchase_order.po_number if receipt.purchase_order else "DIRECT_RECEIPT", details={"reason": data.reason.strip(), "changes": changes, "subtotal": str(receipt.subtotal), "tax_amount": str(receipt.tax_amount), "total_amount": str(receipt.total_amount)})
        db.commit(); db.refresh(receipt); return receipt

    @classmethod
    def return_receipt(cls, db: Session, *, receipt_id: int, user):
        cls._check_access(user, "WAREHOUSE", "PURCHASING")
        receipt = db.query(GoodsReceipt).filter(GoodsReceipt.id == receipt_id).with_for_update().first()
        if not receipt: raise HTTPException(status_code=404, detail="Goods receipt not found")
        if receipt.status != "POSTED": raise HTTPException(status_code=409, detail="Only posted receipts can be returned")
        downstream_invoice = db.query(SupplierInvoice).filter(SupplierInvoice.goods_receipt_id == receipt.id, SupplierInvoice.status.notin_({"VOID", "REJECTED"})).first()
        if downstream_invoice: raise HTTPException(status_code=409, detail=f"Receipt cannot be returned after supplier invoice {downstream_invoice.internal_invoice_number} has been created")
        purchase_order = db.query(PurchaseOrder).filter(PurchaseOrder.id == receipt.purchase_order_id).with_for_update().first() if receipt.purchase_order_id else None
        for receipt_item in receipt.items:
            quantity = Decimal(receipt_item.quantity)
            if receipt.destination_type == "WAREHOUSE":
                inventory = db.query(Inventory).filter(Inventory.product_id == receipt_item.product_id, Inventory.warehouse_id == receipt.warehouse_id).with_for_update().first()
                if not inventory or Decimal(inventory.quantity or 0) < quantity: raise HTTPException(status_code=409, detail=f"Insufficient current stock to return product {receipt_item.product_id}")
                current_qty, current_avg = Decimal(inventory.quantity or 0), Decimal(inventory.average_cost or 0)
                current_value, return_value = current_qty * current_avg, quantity * Decimal(receipt_item.unit_cost or 0)
                new_qty, remaining_value = current_qty - quantity, current_value - return_value
                if new_qty == 0: inventory.quantity, inventory.average_cost = ZERO, ZERO
                else:
                    if remaining_value < ZERO: raise HTTPException(status_code=409, detail=f"Return would make inventory value negative for product {receipt_item.product_id}")
                    inventory.quantity, inventory.average_cost = new_qty, remaining_value / new_qty
                db.add(cls._movement(receipt, receipt_item, "OUT", "GOODS_RECEIPT_RETURN"))
            if purchase_order and receipt_item.purchase_order_item_id:
                po_item = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.id == receipt_item.purchase_order_item_id).with_for_update().first()
                if not po_item: raise HTTPException(status_code=409, detail=f"PO item for receipt line {receipt_item.id} no longer exists")
                po_item.received_quantity = max(ZERO, Decimal(po_item.received_quantity or 0) - quantity)
        if purchase_order:
            purchase_order.status = "RECEIVED" if all(Decimal(item.received_quantity or 0) >= Decimal(item.quantity) for item in purchase_order.items) else "PARTIALLY_RECEIVED" if any(Decimal(item.received_quantity or 0) > 0 for item in purchase_order.items) else "APPROVED"
        receipt.status = "RETURNED"
        ActivityService.log(db=db, user=user, action="RETURN", entity_type="GOODS_RECEIPT", entity_id=receipt.id, summary=f"Returned {receipt.receipt_number}", document_type="GR", document_number=receipt.receipt_number, document_status="RETURNED", reference_document=purchase_order.po_number if purchase_order else "DIRECT_RECEIPT")
        db.commit(); db.refresh(receipt); return receipt
