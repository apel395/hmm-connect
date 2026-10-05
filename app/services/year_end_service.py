from datetime import date
from fastapi import HTTPException
from app.models.fiscal_period import FiscalPeriod
from app.models.fiscal_year_close import FiscalYearClose
from app.services.period_closing_service import PeriodClosingService
from app.services.audit import record_audit


class YearEndService:
    @classmethod
    def close_year(cls, *, db, fiscal_year, closing_date, user):
        periods = db.query(FiscalPeriod).filter_by(fiscal_year=fiscal_year).order_by(FiscalPeriod.start_date).with_for_update().all()
        if {p.fiscal_month for p in periods} != set(range(1, 13)):
            raise HTTPException(409, "Initialize all twelve accounting periods before year closing")
        record = db.query(FiscalYearClose).filter_by(fiscal_year=fiscal_year).with_for_update().first()
        if record and record.is_closed:
            return {"fiscal_year": fiscal_year, "message": "Fiscal year is already closed"}
        ids = []
        for period in periods:
            ids.extend(PeriodClosingService.close(db, period.id, user)["closing_journal_ids"])
        actual_date = date(fiscal_year, 12, 31)
        if not record:
            record = FiscalYearClose(fiscal_year=fiscal_year)
            db.add(record)
        record.closing_date = actual_date
        record.journal_entry_id = ids[-1] if ids else None
        record.is_closed = True
        record_audit(db, user, "FISCAL_YEAR_CLOSED", "FISCAL_YEAR", f"Closed {fiscal_year}",
                     after_data={"closing_journal_ids": ids, "closing_date": actual_date.isoformat()})
        db.commit()
        return {"fiscal_year": fiscal_year, "closing_date": actual_date, "closing_journal_ids": ids, "message": "Fiscal year closed"}
