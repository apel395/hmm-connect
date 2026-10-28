"""Real PostgreSQL row-lock regression tests; never connect to the application DB."""
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Event
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.sales_transaction import SalesTransaction  # noqa: F401 - register POS/AR FK targets
from app.models.accounting_setting import AccountingSetting
from app.models.business_unit import BusinessUnit
from app.models.chart_of_account import ChartOfAccount
from app.models.fiscal_period import FiscalPeriod
from app.models.general_ledger import GeneralLedger
from app.models.journal_entry import JournalEntry
from app.models.journal_line import JournalLine
from app.models.location import Location
from app.models.opening_balance import OpeningBalance
from app.models.user import User

TEST_URL = os.getenv('MMH_PG_TEST_URL')
pytestmark = pytest.mark.skipif(not TEST_URL, reason='Dedicated PostgreSQL concurrency database not configured')


@pytest.fixture
def pg():
    url = make_url(TEST_URL)
    if url.get_backend_name() != 'postgresql' or url.database != 'mmh_journal_concurrency_test':
        pytest.fail('Refusing database: MMH_PG_TEST_URL must target mmh_journal_concurrency_test')
    # Every test owns a separate schema. No application/public tables are used.
    schema = 'journal_test_' + uuid.uuid4().hex
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={'options': f'-csearch_path={schema} -clock_timeout=10000 -cstatement_timeout=20000'})
    try:
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        with factory() as db:
            unit = BusinessUnit(code='HTL', name='Hotel test')
            db.add(unit); db.flush()
            location = Location(code='HTL', name='Hotel test', location_type='HOTEL', business_unit_id=unit.id)
            actor = User(username='concurrency', email='concurrency@example.test', full_name='Concurrency test', password_hash='test-only')
            db.add_all([location, actor]); db.flush()
            accounts = [ChartOfAccount(account_number=number, account_name=name, account_type=kind,
                normal_balance=normal, is_active=True, is_posting=True) for number,name,kind,normal in (
                ('400','Revenue','REVENUE','CREDIT'),('100-110-100','Cash','ASSET','DEBIT'),
                ('300-100-103','Earnings','EQUITY','CREDIT'),('200-100-1','Payable','LIABILITY','CREDIT'),
                ('700-100','Expense','EXPENSE','DEBIT'))]
            accounts[1].account_subtype = 'BANK'
            db.add_all(accounts); db.flush()
            period = FiscalPeriod(fiscal_year=2026, fiscal_month=1, period_name='January test',
                start_date=date(2026,1,1), end_date=date(2026,1,31), is_open=True, is_closed=False, allow_backdated_entries=True)
            db.add_all([period, AccountingSetting(setting_key='CURRENT_YEAR_EARNINGS_ACCOUNT', account_id=accounts[2].id),
                OpeningBalance(fiscal_year=2026, account_id=accounts[1].id, location_id=location.id, amount=1000, balance_type='DEBIT')])
            entry = JournalEntry(journal_number='CONCURRENT-MAN', posting_date=date(2026,1,10), status='DRAFT',
                reference_type='MANUAL', reference_id=0, location_id=location.id, business_unit_id=unit.id, created_by_id=actor.id)
            entry.lines = [JournalLine(account_id=accounts[0].id, debit=0, credit=100, location_id=location.id, business_unit_id=unit.id),
                JournalLine(account_id=accounts[1].id, debit=100, credit=0, location_id=location.id, business_unit_id=unit.id)]
            db.add(entry); db.commit()
            user = SimpleNamespace(id=actor.id, username=actor.username, full_name=actor.full_name,
                roles=[SimpleNamespace(name='SYSTEM_ADMINISTRATOR')], location_id=None, default_location_id=None,
                department_id=None, default_department_id=None, default_business_unit_id=None)
            data = SimpleNamespace(factory=factory, user=user, journal_id=entry.id, period_id=period.id,
                unit_id=unit.id, location_id=location.id, accounts=[account.id for account in accounts])
        yield data
        with factory() as db:
            assert db.query(OpeningBalance).one().amount == Decimal('1000')
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def race(pg, holder_action, waiter_action, holder_finalize=None):
    """Prove the second connection is blocked by the first, then let it proceed."""
    ready, release, started = Event(), Event(), Event()
    pids = {}
    def holder():
        with pg.factory() as db:
            pids['holder'] = db.scalar(text('SELECT pg_backend_pid()'))
            try:
                result = holder_action(db)
                ready.set()
                assert release.wait(12), 'Test failed to release holder transaction'
                if holder_finalize is not None:
                    result = holder_finalize(db)
                db.commit()
                return result
            except Exception:
                db.rollback(); ready.set(); raise
    def waiter():
        assert ready.wait(12)
        with pg.factory() as db:
            pids['waiter'] = db.scalar(text('SELECT pg_backend_pid()'))
            started.set()
            try:
                result = waiter_action(db)
                db.commit()
                return result
            except HTTPException as error:
                db.rollback()
                return error
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(holder)
        assert ready.wait(12)
        if first.done():
            first.result()  # Propagate a holder failure without waiting for a lock.
        second = pool.submit(waiter)
        try:
            assert started.wait(12)
            deadline = time.monotonic() + 8
            blocked = False
            with pg.factory() as observer:
                while time.monotonic() < deadline:
                    blockers = observer.scalar(text('SELECT pg_blocking_pids(:pid)'), {'pid': pids['waiter']})
                    if pids['holder'] in blockers:
                        blocked = True
                        break
                    if second.done():
                        break
                    time.sleep(.025)
            assert blocked, 'Competing transaction did not wait on the accounting lock'
        finally:
            release.set()
        return first.result(timeout=15), second.result(timeout=15)


def post_without_commit(pg, db):
    from app.api.v1.journals import locked_journal, post_locked_journal
    journal = locked_journal(db, pg.journal_id, pg.user)
    post_locked_journal(db, journal=journal, user=pg.user)
    return journal.id


def test_two_connections_cannot_post_same_journal_twice(pg):
    from app.api.v1.journals import post
    _, result = race(pg, lambda db: post_without_commit(pg,db), lambda db: post(pg.journal_id,db=db,user=pg.user))
    assert isinstance(result, HTTPException) and result.status_code == 409
    with pg.factory() as db:
        assert db.get(JournalEntry,pg.journal_id).status == 'POSTED'
        assert db.query(GeneralLedger).count() == 2


def test_post_then_concurrent_close_does_not_post_twice(pg):
    from app.services.period_closing_service import PeriodClosingService
    _, result = race(pg, lambda db: post_without_commit(pg,db), lambda db: PeriodClosingService.close(db,pg.period_id,pg.user))
    assert len(result['closing_journal_ids']) == 1
    with pg.factory() as db:
        assert db.query(GeneralLedger).filter_by(reference_type='MANUAL').count() == 2
        assert db.get(FiscalPeriod,pg.period_id).is_closed


@pytest.mark.parametrize('action',['edit','unpost'])
def test_close_blocks_concurrent_edit_or_unpost(pg,action):
    from app.api.v1.journals import post, update, unpost
    from app.schemas.journal import JournalUpdate
    from app.services.period_closing_service import PeriodClosingService
    if action == 'unpost':
        with pg.factory() as db: post(pg.journal_id,db=db,user=pg.user)
    def attempt(db):
        if action == 'edit':return update(pg.journal_id,JournalUpdate(description='Should not persist'),db=db,user=pg.user)
        return unpost(pg.journal_id,db=db,user=pg.user)
    _, result = race(pg, lambda db: PeriodClosingService.close(db,pg.period_id,pg.user), attempt)
    assert isinstance(result,HTTPException) and result.status_code == 400
    with pg.factory() as db:
        journal=db.get(JournalEntry,pg.journal_id)
        assert journal.status=='POSTED' and journal.description!='Should not persist'
        assert db.query(GeneralLedger).filter_by(reference_type='MANUAL').count()==2


def test_two_concurrent_closes_share_one_closing_entry(pg):
    from app.services.period_closing_service import PeriodClosingService
    first, second = race(pg,lambda db:PeriodClosingService.close(db,pg.period_id,pg.user),lambda db:PeriodClosingService.close(db,pg.period_id,pg.user))
    assert first['closing_journal_ids']==second['closing_journal_ids']
    with pg.factory() as db:
        assert db.query(JournalEntry).filter_by(reference_type='PERIOD_CLOSE',status='POSTED').count()==1
        assert db.query(GeneralLedger).count()==4


def test_double_payment_settlement_updates_invoice_once(pg):
    from app.api.v1.payments import post
    from app.models.bank_account import BankAccount
    from app.models.payment import Payment, PaymentAllocation, PaymentFundingLine
    from app.models.supplier import Supplier
    from app.models.supplier_invoice import SupplierInvoice
    with pg.factory() as db:
        supplier=Supplier(code='SUP',name='Concurrent supplier',payable_account_id=pg.accounts[3])
        bank=BankAccount(bank_name='Test bank',account_name='Test cash',account_number='123',coa_account_id=pg.accounts[1],currency='IDR',is_active=True,is_payment_account=True,business_unit_id=pg.unit_id)
        db.add_all([supplier,bank]);db.flush()
        invoice=SupplierInvoice(internal_invoice_number='INV-TEST',supplier_invoice_number='VENDOR-TEST',supplier_id=supplier.id,
            invoice_date=date(2026,1,10),status='VERIFIED',subtotal=100,total_amount=100,paid_amount=0,balance_amount=100,
            location_id=pg.location_id,business_unit_id=pg.unit_id)
        db.add(invoice);db.flush()
        invoice_journal=JournalEntry(journal_number='INV-JE',posting_date=invoice.invoice_date,status='DRAFT',reference_type='SUPPLIER_INVOICE',reference_id=invoice.id,location_id=pg.location_id,business_unit_id=pg.unit_id)
        invoice_journal.lines=[JournalLine(account_id=pg.accounts[4],debit=100,credit=0),JournalLine(account_id=pg.accounts[3],debit=0,credit=100)]
        payment=Payment(payment_number='PAY-TEST',payment_date=date(2026,1,10),supplier_id=supplier.id,amount=60,status='APPROVED',payment_method='BANK_TRANSFER',created_by_id=pg.user.id,location_id=pg.location_id,business_unit_id=pg.unit_id)
        payment.allocations=[PaymentAllocation(supplier_invoice_id=invoice.id,allocated_amount=60)]
        payment.funding_lines=[PaymentFundingLine(bank_account_id=bank.id,amount=60)]
        db.add_all([invoice_journal,payment]);db.flush()
        journal=JournalEntry(journal_number='PAY-JE',document_type='SUPPLIER_PAYMENT',document_number=payment.payment_number,
            posting_date=payment.payment_date,status='DRAFT',reference_type='SUPPLIER_PAYMENT',reference_id=payment.id,location_id=pg.location_id,business_unit_id=pg.unit_id)
        journal.lines=[JournalLine(account_id=account,debit=debit,credit=credit,location_id=pg.location_id,business_unit_id=pg.unit_id)
            for account,debit,credit in [(pg.accounts[3],60,0),(pg.accounts[1],0,60)]]
        db.add(journal);db.flush();payment.journal_entry_id=journal.id;db.commit()
        payment_id, invoice_id = payment.id,invoice.id
    def hold_payment(db):
        db.query(Payment.id).filter(Payment.id==payment_id).with_for_update().one()
    _, result = race(pg, hold_payment, lambda db: post(payment_id,db=db,user=pg.user),
        holder_finalize=lambda db: post(payment_id,db=db,user=pg.user))
    assert isinstance(result,HTTPException) and result.status_code==409
    with pg.factory() as db:
        invoice=db.get(SupplierInvoice,invoice_id)
        assert invoice.paid_amount==60 and invoice.balance_amount==40
        assert db.query(GeneralLedger).filter_by(reference_type='SUPPLIER_PAYMENT').count()==2

