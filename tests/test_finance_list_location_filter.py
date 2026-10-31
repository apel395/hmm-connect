from types import SimpleNamespace

import pytest

from app.api.v1.journals import listing as journals_listing
from app.api.v1.payments import listing as payments_listing
from app.api.v1.supplier_invoices import listing as supplier_invoices_listing


SUPERUSER = SimpleNamespace(
    roles=[SimpleNamespace(name="SYSTEM_ADMINISTRATOR")],
    default_location_id=None,
    location_id=None,
)


class Query:
    def __init__(self):
        self.filters = []

    def filter(self, *expressions):
        self.filters.extend(expressions)
        return self

    def join(self, *expressions):
        return self

    def options(self, *loaders):
        return self

    def with_entities(self, *entities):
        return self

    def distinct(self):
        return self

    def order_by(self, *expressions):
        return self

    def offset(self, value):
        return self

    def limit(self, value):
        return self

    def count(self):
        return 0

    def all(self):
        return []


class FakeDb:
    def __init__(self):
        self.query_obj = Query()

    def query(self, model):
        return self.query_obj


LISTINGS = [
    ("journals", journals_listing),
    ("supplier_invoices", supplier_invoices_listing),
    ("payments", payments_listing),
]


@pytest.mark.parametrize("name,listing_fn", LISTINGS, ids=[name for name, _ in LISTINGS])
def test_location_filter_applied_when_requested(name, listing_fn):
    db = FakeDb()
    result = listing_fn(
        page=1,
        page_size=20,
        search=None,
        status=None,
        location_id=7,
        db=db,
        user=SUPERUSER,
    )
    assert db.query_obj.filters, f"{name}: expected a location filter when location_id was provided"
    assert result["total_items"] == 0


@pytest.mark.parametrize("name,listing_fn", LISTINGS, ids=[name for name, _ in LISTINGS])
def test_no_location_filter_when_not_requested(name, listing_fn):
    db = FakeDb()
    listing_fn(
        page=1,
        page_size=20,
        search=None,
        status=None,
        location_id=None,
        db=db,
        user=SUPERUSER,
    )
    assert db.query_obj.filters == [], f"{name}: no location filter should be applied when location_id is omitted"
