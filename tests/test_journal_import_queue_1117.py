"""Regression tests for the SSM-free journal import queue.

These exercise the public API functions and the EC2 worker claim with an
isolated database. They never call S3/SSM or post production journals.
"""
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.import_batch import ImportBatch, ImportRow
from app.models.role import Role
from app.models.user import User
from app.api.v1.journal_imports import JournalImportConfirm, confirm_import, start_validation
from app.scripts import journal_import_worker


@pytest.fixture
def context(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(journal_import_worker, "SessionLocal", maker)
    with maker() as db:
        user = User(
            username="journal-queue-test",
            email="journal-queue@example.test",
            full_name="Journal Queue Test",
            password_hash="x",
            roles=[Role(name="SYSTEM_ADMINISTRATOR")],
        )
        db.add(user)
        db.flush()
        user_id = user.id
        db.commit()
    yield maker, user_id
    engine.dispose()


def make_batch(db, *, user_id, batch_id, status, mode="PREVIEW"):
    batch = ImportBatch(
        id=batch_id,
        batch_number=f"JIMP-QUEUE-{batch_id}",
        batch_name="Queue test",
        source="JOURNAL_BULK_IMPORT",
        source_type="JOURNAL_BULK_IMPORT",
        import_type="JOURNAL_ENTRY",
        import_mode=mode,
        created_by_id=user_id,
        imported_by_id=user_id,
        status=status,
    )
    db.add(batch)
    db.commit()
    return batch


def test_validation_enqueue_idempotent_without_ssm(context, monkeypatch):
    maker, user_id = context

    def forbidden(*_args, **_kwargs):
        raise AssertionError("AWS client must never be created by the queue API")

    monkeypatch.setattr("app.services.journal_import_jobs.boto3.client", forbidden)
    with maker() as db:
        make_batch(db, user_id=user_id, batch_id=101, status="UPLOADED")
        actor = SimpleNamespace(id=user_id)
        first = start_validation(101, db=db, user=actor)
        second = start_validation(101, db=db, user=actor)
        assert first["status"] == second["status"] == "QUEUED"
        assert second["worker_command_id"] is None


@pytest.mark.parametrize("post_valid,expected_mode", [(True, "POST"), (False, "DRAFT")])
def test_import_enqueue_preserves_durable_posting_choice(context, post_valid, expected_mode):
    maker, user_id = context
    with maker() as db:
        make_batch(db, user_id=user_id, batch_id=102, status="VALIDATED")
        db.add(ImportRow(
            id=1001,
            import_batch_id=102,
            row_number=2,
            document_type="JOURNAL_ENTRY",
            raw_data_json={},
            normalized_data_json={"_group_key": "DOC-1"},
            status="VALID",
        ))
        db.commit()
        actor = SimpleNamespace(id=user_id)
        first = confirm_import(102, JournalImportConfirm(post_valid=post_valid), db=db, user=actor)
        assert first["status"] == "IMPORT_QUEUED"
        assert db.get(ImportBatch, 102).import_mode == expected_mode
        second = confirm_import(102, JournalImportConfirm(post_valid=post_valid), db=db, user=actor)
        assert second["status"] == "IMPORT_QUEUED"


def test_worker_claims_validation_once(context, monkeypatch):
    maker, user_id = context
    with maker() as db:
        make_batch(db, user_id=user_id, batch_id=103, status="QUEUED")
    called = []

    def fake_validate(db, batch, user):
        called.append(batch.id)
        batch.status = "VALIDATED"
        db.commit()

    monkeypatch.setattr(journal_import_worker, "validate_job", fake_validate)
    assert journal_import_worker.next_queued_job() == (103, "validate")
    assert journal_import_worker.run_job(103, mode="validate") is True
    assert journal_import_worker.run_job(103, mode="validate") is False
    assert called == [103]


def test_worker_import_mode_comes_from_committed_batch_not_ssm_flag(context, monkeypatch):
    maker, user_id = context
    with maker() as db:
        make_batch(db, user_id=user_id, batch_id=104, status="IMPORT_QUEUED", mode="POST")
    observed = []

    def fake_import(db, batch, user, post_valid):
        observed.append(post_valid)
        batch.status = "IMPORTED"
        db.commit()

    monkeypatch.setattr(journal_import_worker, "import_valid_groups", fake_import)
    assert journal_import_worker.next_queued_job() == (104, "import")
    assert journal_import_worker.run_job(104, mode="import", post_valid=False) is True
    assert journal_import_worker.run_job(104, mode="import") is False
    assert observed == [True]
