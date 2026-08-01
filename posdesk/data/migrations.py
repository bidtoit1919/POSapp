from __future__ import annotations

from .database import Database

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS shops (id TEXT PRIMARY KEY, name TEXT NOT NULL, timezone TEXT NOT NULL DEFAULT 'UTC', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE, display_name TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('owner','cashier')), password_hash TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS categories (id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS suppliers (id TEXT PRIMARY KEY, name TEXT NOT NULL, phone TEXT, email TEXT, address TEXT, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS products (id TEXT PRIMARY KEY, name TEXT NOT NULL, sku TEXT NOT NULL UNIQUE, barcode TEXT UNIQUE, category_id TEXT REFERENCES categories(id), unit TEXT NOT NULL DEFAULT 'each', buying_price_minor INTEGER NOT NULL DEFAULT 0 CHECK(buying_price_minor >= 0), selling_price_minor INTEGER NOT NULL CHECK(selling_price_minor >= 0), tax_bps INTEGER NOT NULL DEFAULT 0 CHECK(tax_bps BETWEEN 0 AND 10000), supplier_id TEXT REFERENCES suppliers(id), low_stock_threshold INTEGER NOT NULL DEFAULT 0 CHECK(low_stock_threshold >= 0), active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS inventory (product_id TEXT PRIMARY KEY REFERENCES products(id), quantity INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS customers (id TEXT PRIMARY KEY, name TEXT NOT NULL, phone TEXT UNIQUE, preferred_discount_bps INTEGER NOT NULL DEFAULT 0 CHECK(preferred_discount_bps BETWEEN 0 AND 10000), lifetime_spend_minor INTEGER NOT NULL DEFAULT 0, last_visit_at TEXT, revision_at TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS sales (id TEXT PRIMARY KEY, shop_id TEXT NOT NULL REFERENCES shops(id), bill_number TEXT NOT NULL, sold_at TEXT NOT NULL, business_date TEXT NOT NULL, cashier_id TEXT NOT NULL REFERENCES users(id), customer_id TEXT REFERENCES customers(id), subtotal_minor INTEGER NOT NULL, discount_minor INTEGER NOT NULL DEFAULT 0, tax_minor INTEGER NOT NULL DEFAULT 0, total_minor INTEGER NOT NULL, status TEXT NOT NULL CHECK(status IN ('completed','refunded')), UNIQUE(shop_id, bill_number));
CREATE TABLE IF NOT EXISTS sale_lines (id TEXT PRIMARY KEY, sale_id TEXT NOT NULL REFERENCES sales(id) ON DELETE CASCADE, product_id TEXT REFERENCES products(id), product_name TEXT NOT NULL, sku TEXT NOT NULL, quantity INTEGER NOT NULL CHECK(quantity > 0), unit_price_minor INTEGER NOT NULL, discount_minor INTEGER NOT NULL DEFAULT 0, tax_bps INTEGER NOT NULL, tax_minor INTEGER NOT NULL DEFAULT 0, line_total_minor INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS payments (id TEXT PRIMARY KEY, sale_id TEXT NOT NULL REFERENCES sales(id) ON DELETE CASCADE, method TEXT NOT NULL CHECK(method IN ('cash','upi','card','other')), amount_minor INTEGER NOT NULL CHECK(amount_minor >= 0), recorded_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS stock_movements (id TEXT PRIMARY KEY, product_id TEXT NOT NULL REFERENCES products(id), quantity_delta INTEGER NOT NULL, reason TEXT NOT NULL CHECK(reason IN ('sale','intake','damage','expiry','correction','refund','transfer_out','transfer_in')), reference_id TEXT, note TEXT, actor_id TEXT REFERENCES users(id), occurred_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS stock_intakes (id TEXT PRIMARY KEY, supplier_id TEXT REFERENCES suppliers(id), received_at TEXT NOT NULL, actor_id TEXT REFERENCES users(id), note TEXT);
CREATE TABLE IF NOT EXISTS daily_closings (id TEXT PRIMARY KEY, shop_id TEXT NOT NULL REFERENCES shops(id), business_date TEXT NOT NULL, closed_by TEXT NOT NULL REFERENCES users(id), closed_at TEXT NOT NULL, cash_sales_minor INTEGER NOT NULL, upi_sales_minor INTEGER NOT NULL, card_sales_minor INTEGER NOT NULL, other_sales_minor INTEGER NOT NULL, refunds_minor INTEGER NOT NULL DEFAULT 0, expected_cash_minor INTEGER NOT NULL, counted_cash_minor INTEGER NOT NULL, difference_minor INTEGER NOT NULL, UNIQUE(shop_id, business_date));
CREATE TABLE IF NOT EXISTS audit_events (id TEXT PRIMARY KEY, actor_id TEXT REFERENCES users(id), kind TEXT NOT NULL, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, payload_json TEXT NOT NULL, occurred_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sync_outbox (event_id TEXT PRIMARY KEY, sequence INTEGER NOT NULL UNIQUE, kind TEXT NOT NULL, payload_json TEXT NOT NULL, occurred_at TEXT NOT NULL, delivered_at TEXT);
CREATE TABLE IF NOT EXISTS sync_inbox (event_id TEXT PRIMARY KEY, origin_shop_id TEXT NOT NULL, received_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS remote_sales (origin_shop_id TEXT NOT NULL, remote_sale_id TEXT NOT NULL, bill_number TEXT NOT NULL, business_date TEXT NOT NULL, total_minor INTEGER NOT NULL, payload_json TEXT NOT NULL, received_at TEXT NOT NULL, PRIMARY KEY(origin_shop_id, remote_sale_id));
CREATE INDEX IF NOT EXISTS idx_products_lookup ON products(name, sku, barcode);
CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(shop_id, business_date);
CREATE INDEX IF NOT EXISTS idx_movements_product ON stock_movements(product_id, occurred_at);
"""


def migrate(db: Database) -> None:
    with db.transaction() as conn:
        conn.executescript(SCHEMA)
        if conn.execute("SELECT 1 FROM schema_migrations WHERE version = 1").fetchone() is None:
            conn.execute("INSERT INTO schema_migrations(version, applied_at) VALUES(1, datetime('now'))")
        if conn.execute("SELECT 1 FROM schema_migrations WHERE version = 2").fetchone() is None:
            conn.execute("INSERT INTO schema_migrations(version, applied_at) VALUES(2, datetime('now'))")
