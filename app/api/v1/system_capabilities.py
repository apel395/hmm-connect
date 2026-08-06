from fastapi import APIRouter

router = APIRouter(prefix="/system", tags=["System"])


@router.get("/capabilities")
def capabilities():
    """Describe optional services available to the current runtime.

    Lambda intentionally exposes only lightweight transactional features. The
    EC2 worker will override these flags when its processing routes are enabled.
    """
    return {
        "runtime": "lambda",
        "worker": False,
        "excel_import": False,
        "excel_export": False,
        "financial_export": False,
        "bank_statement_xlsx_import": False,
        "budget_import": False,
        "fixed_asset_processing": False,
        "historical_import": False,
        "scheduled_jobs": False,
    }
