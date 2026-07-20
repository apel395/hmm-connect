from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user

from app.models.item_group import ItemGroup
from app.models.item_subgroup import ItemSubgroup
from app.services.audit import record_audit

from app.schemas.item_classification import (
    ItemGroupCreate,
    ItemGroupResponse,
    ItemSubgroupCreate,
    ItemSubgroupResponse,
)


router = APIRouter(
    prefix="/item-classification",
    tags=["Item Classification"],
)


@router.get(
    "/groups",
    response_model=list[ItemGroupResponse],
)
def get_groups(
    db: Session = Depends(get_db),
):
    return (
        db.query(ItemGroup)
        .filter(ItemGroup.is_active.is_(True))
        .order_by(ItemGroup.code)
        .all()
    )


@router.post(
    "/groups",
    response_model=ItemGroupResponse,
)
def create_group(
    data: ItemGroupCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    existing = (
        db.query(ItemGroup)
        .filter(
            ItemGroup.code == data.code,
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Group code already exists",
        )

    group = ItemGroup(
        code=data.code,
        name=data.name,
    )

    db.add(group)
    db.flush()

    record_audit(
        db=db,
        user=current_user,
        action="CREATE",
        entity_type="ITEM_GROUP",
        entity_id=group.id,
        summary=f"Created item group {group.code} - {group.name}",
        details={"code": group.code, "name": group.name},
    )

    db.commit()
    db.refresh(group)

    return group


@router.get(
    "/subgroups",
    response_model=list[ItemSubgroupResponse],
)
def get_subgroups(
    group_id: int | None = None,
    db: Session = Depends(get_db),
):
    query = (
        db.query(ItemSubgroup)
        .filter(
            ItemSubgroup.is_active.is_(True),
        )
    )

    if group_id:
        query = query.filter(
            ItemSubgroup.group_id == group_id,
        )

    return (
        query
        .order_by(ItemSubgroup.code)
        .all()
    )


@router.post(
    "/subgroups",
    response_model=ItemSubgroupResponse,
)
def create_subgroup(
    data: ItemSubgroupCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    group = (
        db.query(ItemGroup)
        .filter(
            ItemGroup.id == data.group_id,
        )
        .first()
    )

    if not group:
        raise HTTPException(
            status_code=404,
            detail="Group not found",
        )

    existing = (
        db.query(ItemSubgroup)
        .filter(
            ItemSubgroup.code == data.code,
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Subgroup code already exists",
        )

    subgroup = ItemSubgroup(
        code=data.code,
        name=data.name,
        group_id=data.group_id,
    )

    db.add(subgroup)
    db.flush()

    record_audit(
        db=db,
        user=current_user,
        action="CREATE",
        entity_type="ITEM_SUBGROUP",
        entity_id=subgroup.id,
        summary=f"Created item subgroup {subgroup.code} - {subgroup.name}",
        details={"code": subgroup.code, "name": subgroup.name, "group_id": subgroup.group_id},
    )

    db.commit()
    db.refresh(subgroup)

    return subgroup
