from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.dependencies.authorization import has_any_role
from app.models.goods_receipt import GoodsReceipt, GoodsReceiptItem
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.stock_movement import StockMovement
from app.models.supplier import Supplier
from app.models.warehouse import Warehouse
from app.schemas.goods_receipt import GoodsReceiptCreate
from app.services.activity_service import ActivityService
from app.services.document_number import next_document_number


class GoodsReceiptService:
    @staticmethod
    def _number(db: Session) -> str:
        return next_document_number(db, "GR", digits=5, day=True)

    @staticmethod
    def _check_access(user, *roles):
        if not has_any_role(user, *roles):
            raise HTTPException(status_code=403, detail="Receiving access required")

    @staticmethod
    def _validate_destination(db: Session, data: GoodsReceiptCreate):
        if data.destination_type == "WAREHOUSE":
            if data.warehouse_id is None:
                raise HTTPException(status_code=400, detail="Warehouse is required for warehouse receiving")
            if not db.get(Warehouse, data.warehouse_id):
                raise HTTPException(status_code=404, detail="Warehouse not found")

    @classmethod
    def create(cls, db: Session, *, data: GoodsReceiptCreate, user):
        cls._check_access(user, "WAREHOUSE", "PURCHASING")
        cls._validate_destination(db, data)
        from app.services.organization_dimensions import validate_dimensions

        purchase_order = db.get(PurchaseOrder, data.purchase_order_id) if data.purchase_order_id else None
        if data.purchase_order_id:
            if not purchase_order:
                raise HTTPException(status_code=404, detail="Purchase order not found")
            if purchase_order.status not in {"APPROVED", "PARTIALLY_RECEIVED"}:
                raise HTTPException(status_code=409, detail="Only approved purchase orders can be received")
            business_unit_id = data.business_unit_id or purchase_order.business_unit_id
            location_id = data.location_id or purchase_order.location_id
            department_id = data.department_id or purchase_order.department_id
            supplier_id = purchase_order.supplier_id
        else:
            supplier = db.get(Supplier, data.supplier_id)
            if not supplier or not supplier.is_active:
                raise HTTPException(status_code=404, detail="Active supplier not found")
            business_unit_id = data.business_unit_id
            location_id = data.location_id
            department_id = data.department_id
            supplier_id = data.supplier_id

        validate_dimensions(db, business_unit_id, location_id, department_id, True)
        receipt = GoodsReceipt(
            receipt_number=cls._number(db), status="DRAFT",
            purchase_order_id=purchase_order.id if purchase_order else None,
            supplier_id=supplier_id,
            received_by_id=user.id,
            received_at=data.received_at or datetime.now(timezone.utc),
            source_type=data.source_type, external_reference=data.external_reference,
            receipt_type=data.receipt_type, destination_type=data.destination_type,
            warehouse_id=data.warehouse_id if data.destination_type == "WAREHOUSE" else None,
            notes=data.notes, business_unit_id=business_unit_id,
            location_id=location_id, department_id=department_id,
        )

        seen = set()
        for incoming in data.items:
            if purchase_order:
                if incoming.purchase_order_item_id in seen:
                    raise HTTPException(status_code=400, detail="A PO item may appear only once per receipt")
                seen.add(incoming.purchase_order_item_id)
                item = db.get(PurchaseOrderItem, incoming.purchase_order_item_id)
                if not item or item.purchase_order_id != purchase_order.id:
                    raise HTTPException(status_code=400, detail="Receipt item does not belong to the purchase order")
                remaining = Decimal(item.quantity) - Decimal(item.received_quantity or 0)
                if remaining <= 0 or incoming.quantity > remaining:
                    raise HTTPException(status_code=409, detail=f"Quantity exceeds remaining amount for PO item {item.id}")
                receipt.items.append(GoodsReceiptItem(
                    purchase_order_item_id=item.id, product_id=item.product_id,
                    quantity=incoming.quantity, unit_cost=Decimal(item.unit_price),
                ))
            else:
                if incoming.product_id in seen:
                    raise HTTPException(status_code=400, detail="A product may appear only once per direct receipt")
                seen.add(incoming.product_id)
                product = db.get(Product, incoming.product_id)
                if not product:
                    raise HTTPException(status_code=404, detail=f"Product {incoming.product_id} not found")
                receipt.items.append(GoodsReceiptItem(
                    purchase_order_item_id=None, product_id=product.id,
                    quantity=incoming.quantity, unit_cost=Decimal(incoming.unit_cost or 0),
                ))

        db.add(receipt); db.flush()
        ActivityService.log(db=db,user=user,action="CREATE",entity_type="GOODS_RECEIPT",entity_id=receipt.id,summary=f"Created {receipt.receipt_number}",document_type="GR",document_number=receipt.receipt_number,document_status="DRAFT",reference_document=purchase_order.po_number if purchase_order else "DIRECT_RECEIPT",details={"source":"PO" if purchase_order else "DIRECT"})
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

        for receipt_item in receipt.items:
            quantity = Decimal(receipt_item.quantity)
            product_id = receipt_item.product_id
            if purchase_order:
                item = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.id == receipt_item.purchase_order_item_id).with_for_update().first()
                remaining = Decimal(item.quantity) - Decimal(item.received_quantity or 0)
                if quantity <= 0 or quantity > remaining: raise HTTPException(status_code=409, detail=f"Quantity exceeds remaining amount for PO item {item.id}")
                item.received_quantity = Decimal(item.received_quantity or 0) + quantity
                product_id = item.product_id
            if receipt.destination_type == "WAREHOUSE":
                inventory = db.query(Inventory).filter(Inventory.product_id == product_id, Inventory.warehouse_id == receipt.warehouse_id).with_for_update().first()
                if not inventory:
                    inventory = Inventory(product_id=product_id, warehouse_id=receipt.warehouse_id, quantity=Decimal("0"), average_cost=Decimal("0")); db.add(inventory); db.flush()
                old_quantity=Decimal(inventory.quantity or 0); new_quantity=old_quantity+quantity
                inventory.average_cost=((old_quantity*Decimal(inventory.average_cost or 0))+(quantity*Decimal(receipt_item.unit_cost)))/new_quantity
                inventory.quantity=new_quantity
                db.add(StockMovement(product_id=product_id,warehouse_id=receipt.warehouse_id,goods_receipt_id=receipt.id,movement_type="IN",quantity=quantity,unit_cost=receipt_item.unit_cost,reference_type="GOODS_RECEIPT",reference_id=receipt.id))

        if purchase_order:
            purchase_order.status="RECEIVED" if all(Decimal(item.received_quantity or 0)>=Decimal(item.quantity) for item in purchase_order.items) else "PARTIALLY_RECEIVED"
        receipt.status="POSTED"
        ActivityService.log(db=db,user=user,action="POST",entity_type="GOODS_RECEIPT",entity_id=receipt.id,summary=f"Posted {receipt.receipt_number}",document_type="GR",document_number=receipt.receipt_number,document_status="POSTED",reference_document=purchase_order.po_number if purchase_order else "DIRECT_RECEIPT",details={"purchase_order_id":purchase_order.id if purchase_order else None,"warehouse_id":receipt.warehouse_id,"destination_type":receipt.destination_type,"item_count":len(receipt.items)})
        db.commit(); db.refresh(receipt); return receipt

    @classmethod
    def return_receipt(cls, db: Session, *, receipt_id: int, user):
        cls._check_access(user, "WAREHOUSE", "PURCHASING")
        receipt=db.query(GoodsReceipt).filter(GoodsReceipt.id==receipt_id).with_for_update().first()
        if not receipt: raise HTTPException(404,"Goods receipt not found")
        if receipt.status!="POSTED": raise HTTPException(409,"Only posted receipts can be returned")
        purchase_order=db.query(PurchaseOrder).filter(PurchaseOrder.id==receipt.purchase_order_id).with_for_update().first() if receipt.purchase_order_id else None
        for receipt_item in receipt.items:
            quantity=Decimal(receipt_item.quantity); product_id=receipt_item.product_id
            if receipt.destination_type=="WAREHOUSE":
                inventory=db.query(Inventory).filter(Inventory.product_id==product_id,Inventory.warehouse_id==receipt.warehouse_id).with_for_update().first()
                if not inventory or Decimal(inventory.quantity or 0)<quantity: raise HTTPException(409,detail=f"Insufficient current stock to return product {product_id}")
                inventory.quantity=Decimal(inventory.quantity)-quantity
                db.add(StockMovement(product_id=product_id,warehouse_id=receipt.warehouse_id,goods_receipt_id=receipt.id,movement_type="OUT",quantity=quantity,unit_cost=receipt_item.unit_cost,reference_type="GOODS_RECEIPT_RETURN",reference_id=receipt.id))
            if purchase_order and receipt_item.purchase_order_item_id:
                po_item=db.query(PurchaseOrderItem).filter(PurchaseOrderItem.id==receipt_item.purchase_order_item_id).with_for_update().first()
                po_item.received_quantity=max(Decimal("0"),Decimal(po_item.received_quantity or 0)-quantity)
        if purchase_order:
            purchase_order.status="RECEIVED" if all(Decimal(item.received_quantity or 0)>=Decimal(item.quantity) for item in purchase_order.items) else "PARTIALLY_RECEIVED" if any(Decimal(item.received_quantity or 0)>0 for item in purchase_order.items) else "APPROVED"
        receipt.status="RETURNED"
        ActivityService.log(db=db,user=user,action="RETURN",entity_type="GOODS_RECEIPT",entity_id=receipt.id,summary=f"Returned {receipt.receipt_number}",document_type="GR",document_number=receipt.receipt_number,document_status="RETURNED",reference_document=purchase_order.po_number if purchase_order else "DIRECT_RECEIPT")
        db.commit();db.refresh(receipt);return receipt
