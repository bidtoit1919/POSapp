from __future__ import annotations

import secrets
import logging
import json
from posdesk.config import Settings, default_data_dir
from posdesk.data.database import Database
from posdesk.data.migrations import migrate
from posdesk.domain.services import PosService, seed_shop
from posdesk.sync.server import start_server
from posdesk.sync.service import SyncStore
from posdesk.sync.worker import start_worker
from posdesk.ui.app import PosApp

def main() -> None:
    settings = Settings(default_data_dir())
    db = Database(settings.database_path); migrate(db)
    generated = secrets.token_urlsafe(12)
    shop_id, first_password = seed_shop(db, settings.shop_name, generated)
    if first_password: print(f"First-run owner password (change it immediately): {generated}")
    with db.connect() as conn: owner_id = conn.execute("SELECT id FROM users WHERE username='owner'").fetchone()[0]
    # Sync remains unavailable-by-default until an administrator provides mTLS files and config.
    from posdesk.config import SyncSettings
    sync = None; sync_stop = None
    try:
        sync_settings = SyncSettings.load(settings.sync_config_path)
        sync_store = SyncStore(db, shop_id)
        sync = start_server(sync_settings, sync_store)
        sync_stop = start_worker(sync_settings, sync_store)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        # A bad peer configuration must never stop local billing.
        logging.basicConfig(filename=settings.data_dir / "shoppos.log", level=logging.INFO)
        logging.exception("Sync disabled; local POS remains available: %s", exc)
    PosApp(PosService(db, shop_id), owner_id).mainloop()
    if sync_stop: sync_stop.set()
    if sync: sync[0].shutdown()

if __name__ == "__main__": main()
