
import pytest

from approval_store import ApprovalStore
from approval_store_factory import make_approval_store


def test_default_uses_sqlite(monkeypatch, tmp_path):
    monkeypatch.delenv(
        "APPROVAL_STORE_BACKEND",
        raising=False
    )

    monkeypatch.setenv(
        "APPROVAL_DB_PATH",
        str(tmp_path / "selection.sqlite3")
    )

    # Even with a Neon URL, default is SQLite.
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://unused:unused@localhost/test"
    )

    store = make_approval_store()

    assert isinstance(store, ApprovalStore)


def test_postgres_can_be_selected(monkeypatch):
    import postgres_approval_store

    monkeypatch.setenv(
        "APPROVAL_STORE_BACKEND",
        "postgres"
    )

    fake_store = object()

    monkeypatch.setattr(
        postgres_approval_store,
        "PostgresApprovalStore",
        lambda: fake_store
    )

    assert make_approval_store() is fake_store


def test_invalid_backend_is_rejected(monkeypatch):
    monkeypatch.setenv(
        "APPROVAL_STORE_BACKEND",
        "unknown"
    )

    with pytest.raises(
        ValueError,
        match="Unsupported approval store backend"
    ):
        make_approval_store()
