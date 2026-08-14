from fastapi import APIRouter

router = APIRouter(prefix="/system", tags=["System"])


@router.get("/capabilities")
def capabilities():
    """Describe optional runtime capabilities exposed by the Lambda API."""
    return {
        "runtime": "lambda",
        "worker": False,
        "trial_balance": True,
        "fixed_assets": True,
        "depreciation": True,
        "amortization": True,
        "bank_reconciliation": True,
        "bank_statement_csv_import": True,
        "spreadsheet_import": False,
        "spreadsheet_export": False,
        "historical_import": False,
        "scheduled_jobs": False,
    }
