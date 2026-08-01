from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from posdesk.domain.exporting import export_sales_csv
from posdesk.data.database import Database
from posdesk.data.migrations import migrate
from posdesk.domain.services import CartLine, PosError, PosService, seed_shop
from posdesk.sync.protocol import Envelope
from posdesk.sync.service import SyncStore

class PosTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.db = Database(Path(self.temp.name) / "db.sqlite3"); migrate(self.db)
        self.shop, self.owner = seed_shop(self.db, "Test shop", "long-safe-password")
        self.service = PosService(self.db, self.shop); self.product = self.service.add_product("Rice", "RICE-1", 12500, quantity=4, tax_bps=500)
    def tearDown(self): self.temp.cleanup()
    def test_sale_atomically_updates_inventory_and_customer(self):
        customer = self.service.create_customer("Ada", "111")
        sale = self.service.complete_sale(self.owner, [CartLine(self.product, 2)], "cash", customer)
        self.assertEqual(sale["total_minor"], 26250)
        with self.db.connect() as c:
            self.assertEqual(c.execute("SELECT quantity FROM inventory WHERE product_id=?", (self.product,)).fetchone()[0], 2)
            self.assertEqual(c.execute("SELECT lifetime_spend_minor FROM customers WHERE id=?", (customer,)).fetchone()[0], 26250)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM payments").fetchone()[0], 1)
    def test_insufficient_stock_leaves_no_sale(self):
        with self.assertRaises(PosError): self.service.complete_sale(self.owner, [CartLine(self.product, 5)], "cash")
        with self.db.connect() as c: self.assertEqual(c.execute("SELECT COUNT(*) FROM sales").fetchone()[0], 0)
    def test_daily_close_requires_owner_and_records_variance(self):
        self.service.complete_sale(self.owner, [CartLine(self.product, 1)], "cash")
        close = self.service.close_day(self.owner, 14000)
        self.assertEqual(close["expected_cash_minor"], 13125); self.assertEqual(close["difference_minor"], 875)
    def test_export_is_human_accessible_csv(self):
        self.service.complete_sale(self.owner, [CartLine(self.product, 1)], "upi")
        output = Path(self.temp.name) / "sales.csv"
        self.assertEqual(export_sales_csv(self.db, output, "2000-01-01", "2999-12-31"), 1)
        self.assertIn("Bill Number", output.read_text(encoding="utf-8"))
    def test_sync_receipt_is_deduplicated_and_isolated_from_local_sales(self):
        payload = {"sale": {"id": "remote-sale", "bill_number": "REMOTE-1", "business_date": "2026-01-01", "total_minor": 100, "lines": []}}
        event = Envelope("event-1", "another-shop", 1, "2026-01-01T00:00:00Z", "sale.completed", payload).as_dict()
        store = SyncStore(self.db, self.shop)
        self.assertTrue(store.accept(event, ("another-shop",)))
        self.assertFalse(store.accept(event, ("another-shop",)))
        with self.db.connect() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM remote_sales").fetchone()[0], 1)
            self.assertEqual(c.execute("SELECT COUNT(*) FROM sales").fetchone()[0], 0)
    def test_owner_can_sign_in(self):
        self.assertIsNotNone(self.service.authenticate("owner", "long-safe-password"))
        self.assertIsNone(self.service.authenticate("owner", "not-the-password"))
    def test_barcode_lookup_and_inventory_editing(self):
        product = self.service.add_product("Tea", "TEA-1", 5000, quantity=3, barcode="8901234567890", low_stock_threshold=2)
        self.assertEqual(self.service.find_product_by_code("8901234567890")["id"], product)
        self.assertEqual(self.service.find_product_by_code("TEA-1")["id"], product)
        self.service.update_product(self.owner, product, name="Premium Tea", sku="TEA-2", barcode="8901234567891", selling_price_minor=5500, buying_price_minor=4000, tax_bps=500, low_stock_threshold=4)
        self.service.adjust_stock(self.owner, product, 7, "intake", "delivery received")
        updated = next(row for row in self.service.list_inventory() if row["id"] == product)
        self.assertEqual((updated["name"], updated["quantity"], updated["selling_price_minor"]), ("Premium Tea", 10, 5500))
    def test_migration_is_safe_on_an_existing_database(self):
        migrate(self.db)
        with self.db.connect() as c:
            self.assertIsNotNone(c.execute("SELECT 1 FROM shops WHERE id=?", (self.shop,)).fetchone())

if __name__ == "__main__": unittest.main()
