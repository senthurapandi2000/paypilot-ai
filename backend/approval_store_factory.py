
import os

from approval_store import ApprovalStore


def make_approval_store():
    backend = os.getenv(
        "APPROVAL_STORE_BACKEND", "sqlite"
    ).strip().lower()

    if backend == "sqlite":
        return ApprovalStore()

    if backend == "postgres":
        from postgres_approval_store import (
            PostgresApprovalStore
        )
        return PostgresApprovalStore()

    raise ValueError(
        f"Unsupported approval store backend: {backend}"
    )
