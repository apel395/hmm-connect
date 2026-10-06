from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.business_unit import BusinessUnit
from app.models.department import Department
from app.models.location_department import LocationDepartment
from app.schemas.organization_dimensions import LocationCreate, LocationUpdate
from app.api.v1 import organization_dimensions as api
from app.services.organization_dimensions import validate_dimensions


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    monkeypatch.setattr(api, "require_access", lambda *args, **kwargs: None)
    monkeypatch.setattr(api, "record_audit", lambda *args, **kwargs: None)
    session.add_all([BusinessUnit(id=1, code="U1", name="Unit 1"), BusinessUnit(id=2, code="U2", name="Unit 2"),
        Department(id=1, code="D1", name="Unit department", business_unit_id=1),
        Department(id=2, code="D2", name="Shared department"),
        Department(id=3, code="D3", name="Other department", business_unit_id=2),
        Department(id=4, code="D4", name="Inactive", business_unit_id=1, is_active=False)])
    session.commit()
    yield session
    session.close()


def create(db, ids):
    return api.create_location(LocationCreate(code="NEW", name="New location", business_unit_id=1, department_ids=ids), db, SimpleNamespace())


def test_create_edit_and_journal_location_lookup(db):
    row = create(db, [1, 2, 1])
    assert row["department_ids"] == [1, 2]
    assert [d["id"] for d in api.list_departments(location_id=row["id"], is_active=True, db=db, user=SimpleNamespace())] == [1, 2]
    assert validate_dimensions(db, 1, row["id"], 1) == (1, row["id"], 1)
    row = api.update_location(row["id"], LocationUpdate(department_ids=[2]), db, SimpleNamespace())
    assert row["department_ids"] == [2]
    with pytest.raises(HTTPException, match="Department is not available"):
        validate_dimensions(db, 1, row["id"], 1)
    # Ordinary edits preserve assignments; empty selection explicitly clears them.
    assert api.update_location(row["id"], LocationUpdate(city="New city"), db, SimpleNamespace())["department_ids"] == [2]
    assert api.update_location(row["id"], LocationUpdate(department_ids=[]), db, SimpleNamespace())["department_ids"] == []
    assert db.query(LocationDepartment).count() == 0


@pytest.mark.parametrize("ids", [[3], [4], [999]])
def test_invalid_assignments_rejected_before_creation(db, ids):
    with pytest.raises(HTTPException):
        create(db, ids)
    assert db.query(LocationDepartment).count() == 0


def test_business_unit_change_cannot_keep_incompatible_department(db):
    row = create(db, [1, 2])
    with pytest.raises(HTTPException):
        api.update_location(row["id"], LocationUpdate(business_unit_id=2), db, SimpleNamespace())
    row = api.update_location(row["id"], LocationUpdate(business_unit_id=2, department_ids=[2, 3]), db, SimpleNamespace())
    assert row["department_ids"] == [2, 3]
