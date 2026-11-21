"""Shared test helpers: a temporary database and a small enquiry fixture."""

from __future__ import annotations

import tempfile
from pathlib import Path

from clientflow.core.db import open_db


class TempDB:
    def __init__(self) -> None:
        self.dir = Path(tempfile.mkdtemp())
        self.path = self.dir / "test.db"
        self.db = open_db(str(self.path))

    def close(self) -> None:
        try:
            self.db.close()
        finally:
            self.path.unlink(missing_ok=True)


ENQUIRY = {
    "id": "ENQ-T1",
    "received_at": "2026-11-20T10:15:00+04:00",
    "source": "contact_form",
    "name": "Test Client",
    "email": "t.client@example.ae",
    "phone": "+971 50 000 0001",
    "message": "We need help setting up a company in a free zone and a trade licence.",
    "documents_supplied": ["trade_licence"],
}
