"""Unit tests for database session scaffolding."""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

import prm.infrastructure.db.models  # noqa: F401 — register metadata
from prm.infrastructure.db.base import Base
from prm.infrastructure.db.session import get_session_factory


def test_base_metadata_registers_users_table() -> None:
    assert "users" in Base.metadata.tables


def test_session_factory_runs_query_against_sqlite() -> None:
    engine = create_engine("sqlite:///:memory:")
    session_factory = get_session_factory(engine)

    with session_factory() as session:
        result = session.execute(text("SELECT 1")).scalar()

    assert result == 1
    assert isinstance(session, Session)
