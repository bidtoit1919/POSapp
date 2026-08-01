from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4


def new_id() -> str: return str(uuid4())
def utc_now() -> str: return datetime.now(UTC).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
def business_date() -> str: return datetime.now().date().isoformat()
