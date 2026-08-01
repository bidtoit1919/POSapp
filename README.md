# ShopPOS

ShopPOS is a local-first desktop POS foundation for small retailers.  It is deliberately designed so that a cashier can launch one application and bill without needing a network, database server, or technical setup.

## Architecture decisions

| Concern | Decision | Why |
| --- | --- | --- |
| Desktop UI | Python standard-library Tkinter, themed conservatively | It is bundled with Python, fast to start, low-memory, and packages reliably for Windows and Linux. A future Qt UI can consume the same services without changing business logic. |
| Storage | One SQLite database per shop, WAL mode, foreign keys, migrations | ACID transactions, no server process, crash-safe commits, and excellent performance on modest hardware. |
| Business logic | UI-independent services and repositories | Checkout rules are testable and reusable by sync/API code. |
| Networking | Optional HTTPS JSON sync service, never database networking | Shops keep operating independently; the only network surface is explicit, authenticated data exchange. |
| Packaging | PyInstaller one-folder build with a launcher | Bundles the interpreter and Tk; users do not install Python or dependencies. One-folder is more reliable and faster to launch than one-file extraction. |

Current implementation provides the production-shaped local core: migrated SQLite data, users/password hashes, inventory, atomic checkout, payment recording, customer totals, stock intake/adjustments, daily close, CSV export, audit events, and a starter desktop workflow. It also includes an HTTPS mutual-TLS sync server and transactional inbox/outbox replication for selected cross-shop sales data.

## Folder layout

```text
posdesk/
  config.py              settings and data-path resolution
  data/                  SQLite connection, migrations, repositories
  domain/                validation, money, auth, POS services
  sync/                  versioned request/envelope protocol
  ui/                    Tkinter application and screens
  main.py                executable entry point
docs/architecture.md     complete product design
tests/                   automated local-core tests
scripts/package.py       PyInstaller packaging command
```

## Development

Requires Python 3.11+ with Tk support. The product build includes Python, so this is only a developer requirement.

```bash
python -m unittest discover -s tests -v
python -m posdesk.main
python scripts/package.py
```

The first launch creates a database under the platform data directory and an owner account. The temporary first-run password is shown once in the console only for development; a polished onboarding screen should require it to be changed before normal use.

## Installation and desktop launch

Build on each target operating system with `python scripts/package.py`. It produces sibling `dist/ShopPOS` and `dist/installer` folders. On Windows, double-click `dist/installer/install-windows-desktop.bat`; on Linux, run `dist/installer/install-linux-desktop.sh` once (or have the installer do so). Both create a `ShopPOS` desktop shortcut that targets the executable in its installed folder. After that, employees only double-click the desktop icon.

To enable HTTPS sync, an administrator copies [sync-config.example.json](/home/ubuntu/shopPOS/sync-config.example.json) to the ShopPOS data directory as `sync-config.json`, replaces the certificate paths and peer shop IDs, and restarts the app. The service refuses to start without a server certificate, key, CA trust root, and a client certificate from that CA.

## Operational safeguards

Back up the database only through the application’s SQLite online-backup workflow (to be exposed in Settings), not by copying a live `-wal` file. Every sale is one SQLite transaction: receipt, lines, inventory movements, payment, customer aggregate, and audit event commit together or not at all.
