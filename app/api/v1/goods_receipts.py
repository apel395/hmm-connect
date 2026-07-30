from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.goods_receipt import GoodsReceipt
from app.schemas.goods_receipt import GoodsReceiptCreate
from app.services.goods_receipt_service import GoodsReceiptService


router = APIRouter(prefix="/goods-receipts", tags=["Goods Receipts"])


@router.get("")
def list_receipts(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(GoodsReceipt).order_by(GoodsReceipt.id.desc()).all()


@router.post("", status_code=201)
def receive_goods(
    data: GoodsReceiptCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return GoodsReceiptService.receive(db=db, data=data, user=user)
