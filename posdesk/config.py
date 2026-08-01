from __future__ import annotations

import os
import json
from dataclasses import dataclass
from pathlib import Path


def default_data_dir() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ShopPOS"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "shoppos"


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    shop_name: str = "My Shop"
    currency: str = "INR"

    @property
    def database_path(self) -> Path:
        return self.data_dir / "shoppos.sqlite3"

    @property
    def sync_config_path(self) -> Path:
        return self.data_dir / "sync-config.json"


@dataclass(frozen=True)
class SyncSettings:
    enabled: bool
    host: str = "127.0.0.1"
    port: int = 8443
    certificate: Path | None = None
    private_key: Path | None = None
    ca_certificate: Path | None = None
    peer_url: str | None = None
    allowed_peer_shop_ids: tuple[str, ...] = ()

    @classmethod
    def load(cls, path: Path) -> "SyncSettings":
        if not path.exists(): return cls(False)
        value = json.loads(path.read_text(encoding="utf-8"))
        def path_value(key: str) -> Path | None:
            return Path(value[key]).expanduser() if value.get(key) else None
        return cls(bool(value.get("enabled", False)), value.get("host", "127.0.0.1"), int(value.get("port", 8443)), path_value("certificate"), path_value("private_key"), path_value("ca_certificate"), value.get("peer_url"), tuple(value.get("allowed_peer_shop_ids", [])))
