from __future__ import annotations

import json
import ssl
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from posdesk.config import SyncSettings
from .service import SyncError, SyncStore


class SyncServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], store: SyncStore, allowed_origins: tuple[str, ...]):
        super().__init__(address, SyncHandler); self.store, self.allowed_origins = store, allowed_origins


class SyncHandler(BaseHTTPRequestHandler):
    server: SyncServer
    protocol_version = "HTTP/1.1"
    def log_message(self, _format: str, *_args: object) -> None: pass  # audit auth failures in production logging
    def _json(self, status: int, value: dict) -> None:
        raw = json.dumps(value, separators=(",", ":")).encode(); self.send_response(status); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def do_GET(self) -> None:
        if self.path == "/v1/sync/status": self._json(200, {"status": "ok"})
        else: self._json(404, {"error": "not_found"})
    def do_POST(self) -> None:
        if self.path != "/v1/sync/push": self._json(404, {"error": "not_found"}); return
        size = int(self.headers.get("Content-Length", "0"))
        if not 0 < size <= 1_000_000: self._json(413, {"error": "invalid_payload_size"}); return
        try:
            events = json.loads(self.rfile.read(size))["events"]
            if not isinstance(events, list) or len(events) > 100: raise ValueError("Invalid event list")
            acknowledged = []
            for event in events:
                self.server.store.accept(event, self.server.allowed_origins); acknowledged.append(event["event_id"])
            self._json(200, {"acknowledged": acknowledged})
        except (ValueError, KeyError, TypeError, SyncError) as exc: self._json(400, {"error": str(exc)})


def start_server(settings: SyncSettings, store: SyncStore) -> tuple[SyncServer, threading.Thread] | None:
    if not settings.enabled: return None
    if not all((settings.certificate, settings.private_key, settings.ca_certificate)): raise ValueError("HTTPS sync requires certificate, private key, and CA certificate")
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(str(settings.certificate), str(settings.private_key))
    context.load_verify_locations(cafile=str(settings.ca_certificate)); context.verify_mode = ssl.CERT_REQUIRED
    server = SyncServer((settings.host, settings.port), store, settings.allowed_peer_shop_ids)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, name="shoppos-https-sync", daemon=True); thread.start()
    return server, thread
