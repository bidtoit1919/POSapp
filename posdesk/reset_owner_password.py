"""Local administrator recovery utility; run only with the POS application closed."""
from __future__ import annotations

from getpass import getpass

from posdesk.config import Settings, default_data_dir
from posdesk.data.database import Database
from posdesk.data.migrations import migrate
from posdesk.domain.auth import hash_password


def main() -> None:
    print("ShopPOS owner password recovery")
    print("Run this only on the shop computer and only when ShopPOS is closed.")
    username = input("Owner username [owner]: ").strip() or "owner"
    password = getpass("New password (at least 10 characters): ")
    confirm = getpass("Confirm new password: ")
    if password != confirm:
        raise SystemExit("Passwords did not match; no change was made.")
    try:
        encoded = hash_password(password)
    except ValueError as exc:
        raise SystemExit(f"No change was made: {exc}") from exc
    db = Database(Settings(default_data_dir()).database_path)
    migrate(db)
    with db.transaction() as conn:
        result = conn.execute("UPDATE users SET password_hash=? WHERE username=? AND role='owner' AND active=1", (encoded, username))
        if result.rowcount != 1:
            raise SystemExit("No active owner account with that username was found; no change was made.")
    print("Owner password changed successfully. Start ShopPOS and sign in.")


if __name__ == "__main__":
    main()
