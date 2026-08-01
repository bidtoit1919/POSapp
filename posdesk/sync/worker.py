from __future__ import annotations

import logging
import ssl
import threading

from posdesk.config import SyncSettings
from .service import SyncError, SyncStore, push

LOG = logging.getLogger(__name__)


def client_context(settings: SyncSettings) -> ssl.SSLContext:
    if not all((settings.certificate, settings.private_key, settings.ca_certificate)):
        raise ValueError("HTTPS sync requires certificate, private key, and CA certificate")
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=str(settings.ca_certificate))
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(str(settings.certificate), str(settings.private_key))
    return context


def start_worker(settings: SyncSettings, store: SyncStore, interval_seconds: int = 60) -> threading.Event | None:
    """Best-effort sender. Checkout only appends the outbox and never waits for this thread."""
    if not settings.enabled or not settings.peer_url: return None
    context = client_context(settings); stop = threading.Event()
    def run() -> None:
        while not stop.is_set():
            try: store.mark_delivered(push(settings.peer_url, store.pending(), context))
            except SyncError as exc: LOG.info("Sync deferred: %s", exc)
            stop.wait(interval_seconds)
    threading.Thread(target=run, name="shoppos-sync-worker", daemon=True).start()
    return stop
