from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

PROTOCOL_VERSION = 1

@dataclass(frozen=True)
class Envelope:
    event_id: str; origin_shop_id: str; sequence: int; occurred_at: str; kind: str; payload: dict
    def as_dict(self) -> dict:
        canonical = json.dumps(self.payload, sort_keys=True, separators=(",", ":")).encode()
        return {"protocol": PROTOCOL_VERSION, "event_id": self.event_id, "origin_shop_id": self.origin_shop_id, "sequence": self.sequence, "occurred_at": self.occurred_at, "kind": self.kind, "payload": self.payload, "payload_sha256": hashlib.sha256(canonical).hexdigest()}

def validate_envelope(value: dict) -> None:
    if value.get("protocol") != PROTOCOL_VERSION or value.get("kind") not in {"sale.completed", "customer.updated", "daily.closed"}: raise ValueError("Unsupported sync envelope")
    canonical = json.dumps(value.get("payload"), sort_keys=True, separators=(",", ":")).encode()
    if hashlib.sha256(canonical).hexdigest() != value.get("payload_sha256"): raise ValueError("Invalid payload hash")
