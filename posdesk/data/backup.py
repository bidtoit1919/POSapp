from __future__ import annotations

import sqlite3
from pathlib import Path
from .database import Database


def create_backup(db: Database, destination: Path) -> None:
    """Use SQLite's online backup API so WAL state is included consistently."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    source = db.connect(); target = sqlite3.connect(destination)
    try: source.backup(target)
    finally: target.close(); source.close()
