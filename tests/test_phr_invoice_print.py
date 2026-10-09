from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.v1.ar_invoice_print import InvoiceDocument, InvoiceLayout, invoice, update_document, update_layout


def document():
    return InvoiceDocument(lines=[dict(registration_number="REG-1", description="Catering", amount="100.00")], tax_amount="10.00", tax_label="PB1")


def db_for(amount="110.00", configuration=None):
    db = MagicMock()
    ar = SimpleNamespace(id=7, customer_id=3, amount=Decimal(amount), invoice_number="AR-7", invoice_date=None,
        due_date=None, received_amount=Decimal("0"), outstanding_amount=Decimal(amount),
        customer=SimpleNamespace(customer_name="PHR", address="Jakarta"))
    layout = SimpleNamespace(configuration=configuration or {})
    db.get.side_effect = [ar, layout]
    db.query.return_value.filter_by.return_value.with_for_update.return_value.first.return_value = layout
    return db, layout


@pytest.mark.parametrize("data", [{"tax_amount":"-1"}, {"lines":[{"description":"A","amount":"1.001"}]}, {"lines":[{"description":"","amount":"1"}]}])
def test_invalid_print_amounts_and_descriptions(data):
    with pytest.raises(ValidationError):
        InvoiceDocument(**data)


def test_document_total_uses_decimal():
    assert document().total() == Decimal("110.00")


def test_save_details_preserves_client_settings_and_other_invoices():
    db, layout = db_for(configuration={"template":"phr", "invoice_documents":{"8":{"description":"Other"}}})
    with patch("app.api.v1.ar_invoice_print.consolidated"), patch("app.api.v1.ar_invoice_print.record_audit"):
        update_document(7, document(), db, object())
    assert layout.configuration["template"] == "phr"
    assert layout.configuration["invoice_documents"]["8"] == {"description":"Other"}
    assert layout.configuration["invoice_documents"]["7"]["tax_amount"] == "10.00"
    db.commit.assert_called_once()


@pytest.mark.parametrize("amount", ["109.99", "110.01"])
def test_mismatch_never_commits(amount):
    db, _ = db_for(amount)
    with patch("app.api.v1.ar_invoice_print.consolidated"), pytest.raises(HTTPException) as exc:
        update_document(7, document(), db, object())
    assert exc.value.status_code == 422
    db.commit.assert_not_called()


def test_client_save_does_not_erase_invoice_details():
    db, layout = db_for(configuration={"invoice_documents":{"7":document().model_dump(mode="json")}})
    with patch("app.api.v1.ar_invoice_print.consolidated"), patch("app.api.v1.ar_invoice_print.record_audit"):
        update_layout(3, InvoiceLayout(template="phr"), db, object())
    assert layout.configuration["invoice_documents"]["7"]["tax_label"] == "PB1"


def test_saved_document_readiness_and_no_historical_defaults():
    db, _ = db_for(configuration={"template":"phr", "invoice_documents":{"7":document().model_dump(mode="json")}})
    with patch("app.api.v1.ar_invoice_print.consolidated"):
        result = invoice(7, db, object())
    assert result["print_ready"]
    assert result["layout"]["contract_number"] == ""
    db, _ = db_for(configuration={"template":"phr"})
    with patch("app.api.v1.ar_invoice_print.consolidated"):
        assert not invoice(7, db, object())["print_ready"]
