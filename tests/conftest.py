"""
Shared pytest configuration for the payment-gateway test suite.

Registers a SQLAlchemy DDL listener that remaps PostgreSQL-only JSONB
columns to plain JSON before schema creation, so that all tests can run
against an in-memory SQLite database without requiring a live PostgreSQL
server.
"""

from sqlalchemy import JSON, event
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base


def _remap_jsonb_to_json(target, connection, **kw):
    """
    Replace JSONB column types with JSON so SQLite can create the schema.
    Called via SQLAlchemy's 'before_create' metadata event.
    """
    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()


# Register once at the session level; this fires before any create_all call.
event.listen(Base.metadata, "before_create", _remap_jsonb_to_json)
