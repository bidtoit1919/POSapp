# ShopPOS product architecture

## Boundaries and runtime topology

Each physical shop installs one independent application package and owns exactly one local SQLite database. The desktop process is the source of truth for local sales and stock. Checkout never waits for DNS, internet, a remote shop, or synchronization.

```text
Cashier UI -> POS service -> SQLite transaction -> local receipt/inventory
                         \
                          -> append-only sync outbox (best effort)

Optional HTTPS peer <-> authenticated sync endpoint <-> validated import transaction
```

The local database is never shared on a network drive and is never exposed as a database listener. A network file share is unsuitable for SQLite reliability and creates a data-loss/security risk.

### Stack and compatibility

Python 3.11+ with Tkinter and SQLite is the initial stack. Tk is intentionally chosen over Electron (large memory footprint) and a web browser shell (more moving parts). The application uses only the standard library at runtime. PyInstaller produces separate Windows and Linux builds on their respective build hosts. Current Python/Tk builds should target supported Windows releases; “older Windows” needs a deliberate legacy release lane with a Python/Tk version that supports the required OS. It is not safe to promise modern security updates on unsupported Windows.

## Data model

IDs are UUIDs generated at the client. Amounts are integer minor units (paise/cents), never floating point. Dates are ISO UTC timestamps; the configured shop time zone controls business-day reports.

| Area | Main tables | Notes |
| --- | --- | --- |
| Identity | `shops`, `users`, `app_settings` | Roles: owner, cashier. Passwords use PBKDF2-HMAC-SHA256 with per-user random salt. |
| Catalogue | `categories`, `products`, `suppliers` | Product includes SKU/barcode, unit, price, tax rate, low-stock threshold and active state. |
| Stock | `inventory`, `stock_movements`, `stock_intakes` | Inventory is a current projection; movements are immutable audit history. |
| Sales | `sales`, `sale_lines`, `payments` | Immutable completed receipts. `sales.bill_number` is unique per shop. |
| Customer | `customers` | Local aggregate is updated in the same sale transaction. Customer sync uses stable UUID and change version. |
| Close/reporting | `daily_closings` | One close per local business date; records expected/count/difference by payment method. |
| Reliability/sync | `audit_events`, `sync_outbox`, `sync_inbox` | Outbox is transactional; inbox de-duplicates event IDs. |

The migrations create the detailed schema used by this foundation. New schema changes must be additive migrations with a monotonic version, tested against an existing database.

## Checkout and inventory rules

1. A cashier creates a draft in memory; it does not reserve stock.
2. Checkout validates user role, active products, positive quantities, and payment total.
3. It starts `BEGIN IMMEDIATE`, rereads inventory, and rejects insufficient stock (unless an owner-approved future negative-stock policy is enabled).
4. It writes sale, lines, payment, negative stock movements, inventory projection, customer aggregate, audit event, and outbox records in the same commit.
5. A receipt is therefore either complete everywhere locally or absent. Power loss before commit cannot leave a completed sale with unadjusted stock.

Refunds are intentionally a future explicit workflow: they must reference original sale lines and produce compensating movements/negative payment records, never edit a historic receipt.

## Synchronization protocol

Synchronization is event replication, not database replication. Every approved record change emits an immutable envelope:

```json
{
  "protocol": 1,
  "event_id": "uuid",
  "origin_shop_id": "uuid",
  "sequence": 41,
  "occurred_at": "2026-08-01T10:00:00Z",
  "kind": "sale.completed",
  "payload": {"...": "selected, versioned data"},
  "payload_sha256": "..."
}
```

The sender performs `POST /v1/sync/push` in small batches. The receiver authenticates it, checks protocol version, signature and payload hash, records `event_id` in `sync_inbox`, then imports in one transaction. Repeated delivery is safe: an already-seen event returns an acknowledgement without repeating work. The receiver returns its cursor/acknowledged IDs; only then is a sender outbox row marked delivered. Pull is the same envelope stream with an opaque per-peer cursor.

Sales and inventory remain shop-owned and are normally exported as read-only cross-shop information. Customers are shared entities: field-level changes include a UTC revision/version and resolve deterministically using latest revision, while preserving a conflict audit record. Inventory transfers will be a two-phase domain event (`transfer.dispatched`, `transfer.received`) rather than direct quantity mutation across databases. Sync runs after UI startup and on a backoff timer; it never runs on the checkout path.

Peer address and TLS credentials live in administrator-managed configuration, not in the cashier UI. The implemented `POST /v1/sync/push` service is wrapped in TLS and requires a valid client certificate signed by the configured CA (mTLS). It accepts at most 100 envelopes/1 MB per request, validates hashes and approved shop IDs, de-duplicates by event ID, and commits the inbox plus remote-sale view in one transaction. LAN discovery can be added later, but a fixed private hostname/configured address is the simpler reliable first option.

## Security

* TLS 1.2+ with certificate pinning or an installed private CA for peer traffic. Each shop gets a distinct client certificate or rotating API credential; do not use one shared permanent secret.
* Mutual TLS is preferred. If token authentication is used, tokens are stored encrypted using OS credential storage where available and rotate/revoke through owner administration.
* The sync endpoint binds only to an explicit LAN interface or approved VPN interface, rate-limits requests, limits JSON size, and logs authentication failures. It has no SQL endpoint and accepts only whitelisted event types.
* Passwords are salted PBKDF2 hashes; access control is enforced in services, not merely hidden UI buttons. Owners perform closing, exports, users, backups, and sync settings; cashiers bill and search approved data.
* Database files and backups receive OS user permissions. Encryption-at-rest can be added via SQLCipher where the deployment threat model needs it; full-disk encryption is the simpler baseline.

## UI design

The home screen is role-based. Cashiers enter a full-screen Billing screen with a large search box, barcode-focus input, product results, a large cart, totals, and three clear payment buttons. Keyboard use is optimized: scan/search, Enter to add, quantity shortcuts, then payment. Owner navigation exposes Dashboard, Inventory, Customers, Suppliers/Intake, Reports, Daily Close, Sync Center, and Settings. All destructive decisions require a plain-language confirmation.

The starter UI implements the essential Billing screen and a small inventory list. UI modules may only call domain services; they must not compose SQL.

## Edge cases and operational policy

* **Duplicate scan:** each scan increments quantity; cashier can edit/remove a line before completion.
* **Two tills at one shop:** this initial product supports one database process per shop. Multi-terminal support needs a local service/database owner or a server database; do not open the SQLite file from multiple networked PCs.
* **Tax/rounding:** retain tax rate captured on every sale line so historical receipts remain correct after product edits. Define jurisdiction-specific inclusive/exclusive calculation and rounding before release.
* **Clock errors:** use local business date consistently; sync records UTC time and detects excessive peer clock skew.
* **Product price changes:** completed sale lines retain their name/SKU/price snapshot.
* **Interrupted print:** sale stays completed; receipt can be reprinted without repeating checkout.
* **Offline peers/conflicts:** queue events, display staleness in Sync Center, and never overwrite shop-owned stock from an inventory lookup.
* **Backups:** scheduled daily versioned backups, restore only when application is closed, and verify a restore copy before replacing live data.
* **Daily closing correction:** close records are immutable; an owner creates a correction/annotation rather than silently edits historic totals.

## Delivery sequence

1. Local core, billing, inventory, users, closing, reports/export, backup/restore.
2. Receipt printing and owner onboarding.
3. Hardened HTTPS sync service, peer provisioning, Sync Center and combined read-only reports.
4. Transfers, purchase orders, loyalty and additional shops.
