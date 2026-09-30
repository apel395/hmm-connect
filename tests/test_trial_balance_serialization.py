from decimal import Decimal

from app.api.v1.trial_balance import serialize


def test_trial_balance_response_serializes_opening_and_closing_sides():
    amounts = {
        "opening_balance": Decimal("125.00"),
        "opening_debit": Decimal("125.00"),
        "opening_credit": Decimal("0.00"),
        "period_debit": Decimal("10.00"),
        "period_credit": Decimal("20.00"),
        "period_total": Decimal("-10.00"),
        "closing_balance": Decimal("115.00"),
        "closing_debit": Decimal("115.00"),
        "closing_credit": Decimal("0.00"),
    }
    report = {
        "items": [dict(amounts)],
        "summary": {
            **amounts,
            "difference": Decimal("-10.00"),
            "opening_difference": Decimal("125.00"),
            "closing_difference": Decimal("115.00"),
        },
    }

    result = serialize(report)

    assert result["items"][0]["opening_debit"] == "125.00"
    assert result["items"][0]["closing_credit"] == "0.00"
    assert result["summary"]["opening_debit"] == "125.00"
    assert result["summary"]["opening_credit"] == "0.00"
    assert result["summary"]["opening_difference"] == "125.00"
    assert result["summary"]["closing_difference"] == "115.00"
