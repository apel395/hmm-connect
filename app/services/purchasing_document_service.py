from calendar import monthrange
from datetime import date
from decimal import Decimal
from math import ceil

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.models.department import Department
from app.models.document_attachment import DocumentAttachment
from app.models.location import Location
from app.models.purchasing_document import PurchasingDocument
from app.models.supplier import Supplier
from app.models.user import User
from app.schemas.purchasing_document import (
    PurchasingDocumentCreate,
    PurchasingDocumentListResponse,
    PurchasingDocumentRead,
    PurchasingDocumentSummary,
    PurchasingDocumentUpdate,
)
from app.services.activity_service import ActivityService


DOCUMENT_TYPES = {"PURCHASE_REQUISITION", "PURCHASE_ORDER"}
SOURCE_TYPES = {"LIVE", "HISTORICAL_IMPORT", "OPENING_BALANCE", "SYSTEM_GENERATED"}
DEFAULT_STAGES = {
    "PURCHASE_REQUISITION": "PLANNED",
    "PURCHASE_ORDER": "COMMITTED",
}


class PurchasingDocumentService:
    @staticmethod
    def _query(db: Session):
        return db.query(PurchasingDocument).options(
            joinedload(PurchasingDocument.supplier),
            joinedload(PurchasingDocument.department),
            joinedload(PurchasingDocument.location),
            joinedload(PurchasingDocument.responsible_user),
        )

    @staticmethod
    def _require_references(db: Session, values: dict) -> None:
        references = (
            ("supplier_id", Supplier, "Supplier"),
            ("department_id", Department, "Department"),
            ("location_id", Location, "Location"),
            ("responsible_user_id", User, "Responsible user"),
        )
        for field, model, label in references:
            value = values.get(field)
            if value is not None and db.get(model, value) is None:
                raise HTTPException(status_code=404, detail=f"{label} not found")

    @staticmethod
    def _validate(values: dict) -> None:
        document_type = values["document_type"]
        if not isinstance(document_type, str):
            raise HTTPException(status_code=400, detail="Document type is required")
        if document_type not in DOCUMENT_TYPES:
            raise HTTPException(status_code=400, detail="Unsupported document type")
        if values.get("source_type") not in SOURCE_TYPES:
            raise HTTPException(status_code=400, detail="Unsupported source type")
        if not isinstance(values.get("status"), str) or not values["status"].strip():
            raise HTTPException(status_code=400, detail="Status is required")
        if values.get("document_date") is None:
            raise HTTPException(status_code=400, detail="Document date is required")
        expected_stage = DEFAULT_STAGES[document_type]
        stage = values.get("cashflow_stage") or expected_stage
        if stage != expected_stage:
            raise HTTPException(
                status_code=400,
                detail=f"{document_type} must use cash-flow stage {expected_stage}",
            )
        values["cashflow_stage"] = stage
        if not isinstance(values.get("document_number"), str) or not values[
            "document_number"
        ].strip():
            raise HTTPException(status_code=400, detail="Document number is required")

    @staticmethod
    def _attachment_count(db: Session, document_id: int) -> int:
        return (
            db.query(func.count(DocumentAttachment.id))
            .filter(
                DocumentAttachment.entity_type == "PURCHASING_DOCUMENT",
                DocumentAttachment.entity_id == document_id,
                DocumentAttachment.is_active.is_(True),
            )
            .scalar()
            or 0
        )

    @classmethod
    def to_read(cls, db: Session, document: PurchasingDocument):
        return PurchasingDocumentRead(
            **{
                column.name: getattr(document, column.name)
                for column in PurchasingDocument.__table__.columns
            },
            supplier_name=document.supplier.name if document.supplier else None,
            department_name=document.department.name if document.department else None,
            location_name=document.location.name if document.location else None,
            responsible_user_name=(
                document.responsible_user.full_name
                if document.responsible_user
                else None
            ),
            attachment_count=cls._attachment_count(db, document.id),
            related_document_count=0,
        )

    @classmethod
    def create(
        cls,
        db: Session,
        data: PurchasingDocumentCreate,
        user: User,
    ):
        values = data.model_dump()
        cls._validate(values)
        cls._require_references(db, values)
        document = PurchasingDocument(**values, created_by=user.id)
        db.add(document)
        db.flush()
        ActivityService.log(
            db=db,
            user=user,
            action="CREATE",
            entity_type="PURCHASING_DOCUMENT",
            entity_id=document.id,
            document_type=document.document_type,
            document_number=document.document_number,
            document_status=document.status,
            summary=f"Created purchasing document {document.document_number}",
            after_data=data.model_dump(mode="json"),
        )
        db.commit()
        return cls.get(db, document.id)

    @classmethod
    def get(cls, db: Session, document_id: int):
        document = cls._query(db).filter(PurchasingDocument.id == document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="Purchasing document not found")
        return document

    @classmethod
    def update(
        cls,
        db: Session,
        document_id: int,
        data: PurchasingDocumentUpdate,
        user: User,
    ):
        document = cls.get(db, document_id)
        before = {
            column.name: getattr(document, column.name)
            for column in PurchasingDocument.__table__.columns
        }
        changes = data.model_dump(exclude_unset=True)
        prospective = {**before, **changes}
        if (
            "total_amount" not in changes
            and ("subtotal" in changes or "tax_amount" in changes)
            and prospective.get("subtotal") is not None
            and prospective.get("tax_amount") is not None
        ):
            changes["total_amount"] = (
                prospective["subtotal"] + prospective["tax_amount"]
            )
            prospective["total_amount"] = changes["total_amount"]
        cls._validate(prospective)
        cls._require_references(db, changes)
        for field, value in changes.items():
            setattr(document, field, value)
        db.flush()
        after = {
            column.name: getattr(document, column.name)
            for column in PurchasingDocument.__table__.columns
        }
        ActivityService.log(
            db=db,
            user=user,
            action="UPDATE",
            entity_type="PURCHASING_DOCUMENT",
            entity_id=document.id,
            document_type=document.document_type,
            document_number=document.document_number,
            document_status=document.status,
            summary=f"Updated purchasing document {document.document_number}",
            before_data=PurchasingDocumentService._json_values(before),
            after_data=PurchasingDocumentService._json_values(after),
        )
        db.commit()
        return cls.get(db, document.id)

    @staticmethod
    def _json_values(values: dict) -> dict:
        return {
            key: (
                value.isoformat()
                if isinstance(value, date)
                else str(value)
                if isinstance(value, Decimal)
                else value
            )
            for key, value in values.items()
        }

    @classmethod
    def set_active(
        cls,
        db: Session,
        document_id: int,
        is_active: bool,
        user: User,
    ):
        document = cls.get(db, document_id)
        if document.is_active == is_active:
            return document
        before = {"is_active": document.is_active}
        document.is_active = is_active
        action = "RESTORE" if is_active else "ARCHIVE"
        ActivityService.log(
            db=db,
            user=user,
            action=action,
            entity_type="PURCHASING_DOCUMENT",
            entity_id=document.id,
            document_type=document.document_type,
            document_number=document.document_number,
            document_status=document.status,
            summary=f"{action.title()}d purchasing document {document.document_number}",
            before_data=before,
            after_data={"is_active": is_active},
        )
        db.commit()
        return cls.get(db, document.id)

    @staticmethod
    def apply_filters(query, filters: dict):
        if filters.get("search"):
            term = f"%{filters['search'].strip()}%"
            query = query.outerjoin(PurchasingDocument.supplier).filter(
                or_(
                    PurchasingDocument.document_number.ilike(term),
                    PurchasingDocument.external_reference.ilike(term),
                    PurchasingDocument.notes.ilike(term),
                    Supplier.name.ilike(term),
                )
            )
        for field in (
            "document_type",
            "status",
            "source_type",
            "supplier_id",
            "department_id",
            "location_id",
            "cashflow_stage",
            "is_active",
        ):
            if filters.get(field) is not None:
                query = query.filter(
                    getattr(PurchasingDocument, field) == filters[field]
                )
        for field, operator, value_key in (
            ("document_date", ">=", "document_date_from"),
            ("document_date", "<=", "document_date_to"),
            ("expected_payment_date", ">=", "expected_payment_date_from"),
            ("expected_payment_date", "<=", "expected_payment_date_to"),
        ):
            value = filters.get(value_key)
            if value is not None:
                column = getattr(PurchasingDocument, field)
                query = query.filter(
                    column >= value if operator == ">=" else column <= value
                )
        return query

    @classmethod
    def list(cls, db: Session, page: int, page_size: int, filters: dict):
        query = cls.apply_filters(cls._query(db), filters)
        total = query.order_by(None).count()
        documents = (
            query.order_by(
                PurchasingDocument.document_date.desc(),
                PurchasingDocument.id.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return PurchasingDocumentListResponse(
            items=[cls.to_read(db, document) for document in documents],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=ceil(total / page_size) if total else 0,
        )

    @classmethod
    def summary(cls, db: Session, filters: dict):
        query = cls.apply_filters(
            db.query(PurchasingDocument).filter(
                PurchasingDocument.is_active.is_(True)
            ),
            {key: value for key, value in filters.items() if key != "is_active"},
        )
        documents = query.all()
        today = date.today()
        month_end = monthrange(today.year, today.month)[1]
        month_start = date(today.year, today.month, 1)
        month_finish = date(today.year, today.month, month_end)
        ids = [document.id for document in documents]
        attached_ids = set()
        if ids:
            attached_ids = {
                value
                for (value,) in db.query(DocumentAttachment.entity_id)
                .filter(
                    DocumentAttachment.entity_type == "PURCHASING_DOCUMENT",
                    DocumentAttachment.entity_id.in_(ids),
                    DocumentAttachment.is_active.is_(True),
                )
                .distinct()
                .all()
            }
        return PurchasingDocumentSummary(
            planned_amount=sum(
                (
                    document.total_amount or Decimal("0")
                    for document in documents
                    if document.cashflow_stage == "PLANNED"
                ),
                Decimal("0"),
            ),
            committed_amount=sum(
                (
                    document.total_amount or Decimal("0")
                    for document in documents
                    if document.cashflow_stage == "COMMITTED"
                ),
                Decimal("0"),
            ),
            expected_this_month=sum(
                (
                    document.total_amount or Decimal("0")
                    for document in documents
                    if document.expected_payment_date
                    and month_start
                    <= document.expected_payment_date
                    <= month_finish
                ),
                Decimal("0"),
            ),
            missing_supplier_count=sum(
                document.supplier_id is None for document in documents
            ),
            missing_amount_count=sum(
                document.total_amount is None for document in documents
            ),
            missing_attachment_count=sum(
                document.id not in attached_ids for document in documents
            ),
            purchase_requisition_count=sum(
                document.document_type == "PURCHASE_REQUISITION"
                for document in documents
            ),
            purchase_order_count=sum(
                document.document_type == "PURCHASE_ORDER"
                for document in documents
            ),
        )
