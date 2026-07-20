from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.location import Location
from app.schemas.location import LocationCreate, LocationResponse, LocationUpdate
from app.services.audit import record_audit

router = APIRouter(prefix="/locations", tags=["Locations"])


@router.get("", response_model=list[LocationResponse])
def get_locations(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return (
        db.query(Location)
        .filter(Location.is_active.is_(True))
        .order_by(Location.name)
        .all()
    )


@router.post("", response_model=LocationResponse, status_code=201)
def create_location(
    data: LocationCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    code = data.code.strip().upper()
    name = data.name.strip()

    if db.query(Location).filter(Location.code == code).first():
        raise HTTPException(status_code=409, detail="Location code already exists")
    if db.query(Location).filter(Location.name == name).first():
        raise HTTPException(status_code=409, detail="Location name already exists")

    location = Location(
        code=code,
        name=name,
        location_type=data.location_type.strip().upper(),
    )
    db.add(location)
    db.flush()

    record_audit(
        db=db,
        user=current_user,
        action="CREATE",
        entity_type="LOCATION",
        entity_id=location.id,
        summary=f"Created location {location.name}",
        details={"code": location.code, "location_type": location.location_type},
    )

    db.commit()
    db.refresh(location)
    return location


@router.patch("/{location_id}", response_model=LocationResponse)
def update_location(
    location_id: int,
    data: LocationUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    location = db.query(Location).filter(Location.id == location_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")

    before = {
        "name": location.name,
        "location_type": location.location_type,
        "is_active": location.is_active,
    }

    if data.name is not None:
        location.name = data.name.strip()
    if data.location_type is not None:
        location.location_type = data.location_type.strip().upper()
    if data.is_active is not None:
        location.is_active = data.is_active

    record_audit(
        db=db,
        user=current_user,
        action="UPDATE",
        entity_type="LOCATION",
        entity_id=location.id,
        summary=f"Updated location {location.name}",
        details={"before": before, "after": {
            "name": location.name,
            "location_type": location.location_type,
            "is_active": location.is_active,
        }},
    )

    db.commit()
    db.refresh(location)
    return location
