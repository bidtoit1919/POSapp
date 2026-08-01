from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from posdesk.data.database import Database
from posdesk.domain.common import utc_now
from .protocol import Envelope, validate_envelope


class SyncError(RuntimeError): pass


class SyncStore:
    """Transactional inbox/outbox operations. It deliberately knows no HTTP details."""
    def __init__(self, db: Database, shop_id: str): self.db, self.shop_id = db, shop_id

    def pending(self, limit: int = 100) -> list[dict]:
        with self.db.connect() as conn:
            rows = conn.execute("SELECT event_id,sequence,kind,payload_json,occurred_at FROM sync_outbox WHERE delivered_at IS NULL ORDER BY sequence LIMIT ?", (limit,)).fetchall()
        return [Envelope(r["event_id"], self.shop_id, r["sequence"], r["occurred_at"], r["kind"], json.loads(r["payload_json"])).as_dict() for r in rows]

    def mark_delivered(self, event_ids: list[str]) -> None:
        if not event_ids: return
        with self.db.transaction() as conn:
            conn.executemany("UPDATE sync_outbox SET delivered_at=? WHERE event_id=?", [(utc_now(), event_id) for event_id in event_ids])

    def accept(self, envelope: dict, allowed_origins: tuple[str, ...] = ()) -> bool:
        validate_envelope(envelope)
        origin, event_id = envelope["origin_shop_id"], envelope["event_id"]
        if origin == self.shop_id or (allowed_origins and origin not in allowed_origins): raise SyncError("Unapproved peer shop")
        with self.db.transaction() as conn:
            if conn.execute("SELECT 1 FROM sync_inbox WHERE event_id=?", (event_id,)).fetchone(): return False
            if envelope["kind"] == "sale.completed":
                sale = envelope["payload"].get("sale", {})
                required = {"id", "bill_number", "business_date", "total_minor"}
                if not required <= sale.keys() or not isinstance(sale["total_minor"], int): raise SyncError("Invalid sale payload")
                conn.execute("INSERT OR IGNORE INTO remote_sales VALUES(?,?,?,?,?,?,?)", (origin, sale["id"], sale["bill_number"], sale["business_date"], sale["total_minor"], json.dumps(envelope["payload"], separators=(",", ":")), utc_now()))
            conn.execute("INSERT INTO sync_inbox VALUES(?,?,?)", (event_id, origin, utc_now()))
        return True


def push(peer_url: str, envelopes: list[dict], ssl_context) -> list[str]:
    if not envelopes: return []
    body = json.dumps({"events": envelopes}, separators=(",", ":")).encode()
    request = Request(peer_url.rstrip("/") + "/v1/sync/push", body, {"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, context=ssl_context, timeout=10) as response:
            if response.status != 200: raise SyncError(f"Peer returned HTTP {response.status}")
            acknowledged = json.loads(response.read())["acknowledged"]
    except (HTTPError, URLError, TimeoutError) as exc: raise SyncError(f"Peer unavailable: {exc}") from exc
    return [str(x) for x in acknowledged]
