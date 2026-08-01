from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable

from posdesk.data.database import Database
from .auth import hash_password, verify_password
from .common import business_date, new_id, utc_now


class PosError(ValueError): pass

@dataclass
class CartLine:
    product_id: str
    quantity: int
    discount_minor: int = 0


class PosService:
    def __init__(self, db: Database, shop_id: str): self.db, self.shop_id = db, shop_id

    def add_product(self, name: str, sku: str, selling_price_minor: int, *, quantity: int = 0,
                    barcode: str | None = None, tax_bps: int = 0, low_stock_threshold: int = 0) -> str:
        if not name.strip() or not sku.strip() or selling_price_minor < 0 or quantity < 0: raise PosError("Invalid product details")
        product_id, now = new_id(), utc_now()
        with self.db.transaction() as c:
            c.execute("INSERT INTO products(id,name,sku,barcode,selling_price_minor,tax_bps,low_stock_threshold,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)", (product_id,name.strip(),sku.strip(),barcode,selling_price_minor,tax_bps,low_stock_threshold,now,now))
            c.execute("INSERT INTO inventory(product_id,quantity,updated_at) VALUES(?,?,?)", (product_id,quantity,now))
            if quantity:
                c.execute("INSERT INTO stock_movements VALUES(?,?,?,?,?,?,?,?)", (new_id(),product_id,quantity,"intake",None,"opening stock",None,now))
        return product_id

    def find_products(self, query: str, limit: int = 30) -> list[dict]:
        term = f"%{query.strip()}%"
        with self.db.connect() as c:
            return [dict(row) for row in c.execute("SELECT p.id,p.name,p.sku,p.barcode,p.selling_price_minor,p.tax_bps,i.quantity FROM products p JOIN inventory i ON i.product_id=p.id WHERE p.active=1 AND (p.name LIKE ? OR p.sku LIKE ? OR p.barcode LIKE ?) ORDER BY p.name LIMIT ?", (term,term,term,limit))]

    def authenticate(self, username: str, password: str) -> dict | None:
        with self.db.connect() as c:
            row = c.execute("SELECT id,display_name,role,password_hash FROM users WHERE username=? AND active=1", (username.strip(),)).fetchone()
        if not row or not verify_password(password, row["password_hash"]): return None
        return {"id": row["id"], "display_name": row["display_name"], "role": row["role"]}

    def create_customer(self, name: str, phone: str | None = None, preferred_discount_bps: int = 0) -> str:
        if not name.strip(): raise PosError("Customer name is required")
        customer_id, now = new_id(), utc_now()
        with self.db.transaction() as c:
            c.execute("INSERT INTO customers(id,name,phone,preferred_discount_bps,revision_at) VALUES(?,?,?,?,?)", (customer_id,name.strip(),phone or None,preferred_discount_bps,now))
        return customer_id

    def complete_sale(self, cashier_id: str, lines: Iterable[CartLine], payment_method: str,
                      customer_id: str | None = None) -> dict:
        lines = list(lines)
        if not lines: raise PosError("Cart is empty")
        if payment_method not in {"cash", "upi", "card", "other"}: raise PosError("Invalid payment method")
        if any(line.quantity <= 0 or line.discount_minor < 0 for line in lines): raise PosError("Invalid cart quantity or discount")
        requested: dict[str, int] = {}
        for line in lines: requested[line.product_id] = requested.get(line.product_id, 0) + line.quantity
        sale_id, now, day = new_id(), utc_now(), business_date()
        with self.db.transaction() as c:
            user = c.execute("SELECT role FROM users WHERE id=? AND active=1", (cashier_id,)).fetchone()
            if not user: raise PosError("Active cashier account required")
            resolved = []
            subtotal = discount = tax = 0
            for line in lines:
                p = c.execute("SELECT p.id,p.name,p.sku,p.selling_price_minor,p.tax_bps,i.quantity FROM products p JOIN inventory i ON i.product_id=p.id WHERE p.id=? AND p.active=1", (line.product_id,)).fetchone()
                if not p: raise PosError("Product is unavailable")
                if p["quantity"] < requested[line.product_id]: raise PosError(f"Insufficient stock: {p['name']}")
                gross = p["selling_price_minor"] * line.quantity
                if line.discount_minor > gross: raise PosError("Discount exceeds line value")
                net = gross - line.discount_minor
                line_tax = (net * p["tax_bps"] + 5000) // 10000
                resolved.append((line,p,gross,line_tax,net + line_tax))
                subtotal += gross; discount += line.discount_minor; tax += line_tax
            total = subtotal - discount + tax
            bill_no = f"{day.replace('-', '')}-{c.execute('SELECT COUNT(*) FROM sales WHERE shop_id=? AND business_date=?', (self.shop_id,day)).fetchone()[0]+1:04d}"
            c.execute("INSERT INTO sales VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (sale_id,self.shop_id,bill_no,now,day,cashier_id,customer_id,subtotal,discount,tax,total,"completed"))
            for line,p,gross,line_tax,line_total in resolved:
                c.execute("INSERT INTO sale_lines VALUES(?,?,?,?,?,?,?,?,?,?,?)", (new_id(),sale_id,p["id"],p["name"],p["sku"],line.quantity,p["selling_price_minor"],line.discount_minor,p["tax_bps"],line_tax,line_total))
                c.execute("UPDATE inventory SET quantity=quantity-?,updated_at=? WHERE product_id=?", (line.quantity,now,p["id"]))
                c.execute("INSERT INTO stock_movements VALUES(?,?,?,?,?,?,?,?)", (new_id(),p["id"],-line.quantity,"sale",sale_id,None,cashier_id,now))
            c.execute("INSERT INTO payments VALUES(?,?,?,?,?)", (new_id(),sale_id,payment_method,total,now))
            if customer_id:
                if c.execute("SELECT 1 FROM customers WHERE id=? AND active=1", (customer_id,)).fetchone() is None: raise PosError("Customer is unavailable")
                c.execute("UPDATE customers SET lifetime_spend_minor=lifetime_spend_minor+?,last_visit_at=?,revision_at=? WHERE id=?", (total,now,now,customer_id))
            payload = json.dumps({"sale": {"id": sale_id, "bill_number": bill_no, "business_date": day, "sold_at": now, "total_minor": total, "payment_method": payment_method, "lines": [{"product_id": p["id"], "name": p["name"], "sku": p["sku"], "quantity": line.quantity, "line_total_minor": line_total} for line, p, _gross, _line_tax, line_total in resolved]}}, separators=(",", ":"))
            c.execute("INSERT INTO audit_events VALUES(?,?,?,?,?,?,?)", (new_id(),cashier_id,"sale.completed","sale",sale_id,payload,now))
            sequence = c.execute("SELECT COALESCE(MAX(sequence),0)+1 FROM sync_outbox").fetchone()[0]
            c.execute("INSERT INTO sync_outbox VALUES(?,?,?,?,?,NULL)", (new_id(),sequence,"sale.completed",payload,now))
        return {"sale_id": sale_id, "bill_number": bill_no, "total_minor": total}

    def adjust_stock(self, actor_id: str, product_id: str, delta: int, reason: str, note: str = "") -> None:
        if not delta or reason not in {"damage","expiry","correction","intake"}: raise PosError("Invalid adjustment")
        now = utc_now()
        with self.db.transaction() as c:
            row = c.execute("SELECT quantity FROM inventory WHERE product_id=?", (product_id,)).fetchone()
            if not row or row[0] + delta < 0: raise PosError("Adjustment would make stock negative")
            c.execute("UPDATE inventory SET quantity=quantity+?,updated_at=? WHERE product_id=?", (delta,now,product_id))
            c.execute("INSERT INTO stock_movements VALUES(?,?,?,?,?,?,?,?)", (new_id(),product_id,delta,reason,None,note,actor_id,now))

    def close_day(self, owner_id: str, counted_cash_minor: int, day: str | None = None) -> dict:
        day = day or business_date()
        if counted_cash_minor < 0: raise PosError("Counted cash cannot be negative")
        with self.db.transaction() as c:
            owner = c.execute("SELECT role FROM users WHERE id=? AND active=1", (owner_id,)).fetchone()
            if not owner or owner[0] != "owner": raise PosError("Owner permission required")
            if c.execute("SELECT 1 FROM daily_closings WHERE shop_id=? AND business_date=?", (self.shop_id,day)).fetchone(): raise PosError("This day is already closed")
            totals = dict(c.execute("SELECT method, COALESCE(SUM(amount_minor),0) total FROM payments p JOIN sales s ON s.id=p.sale_id WHERE s.shop_id=? AND s.business_date=? AND s.status='completed' GROUP BY method", (self.shop_id,day)).fetchall())
            cash,upi,card,other = (totals.get(k,0) for k in ("cash","upi","card","other"))
            difference = counted_cash_minor - cash
            c.execute("INSERT INTO daily_closings VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (new_id(),self.shop_id,day,owner_id,utc_now(),cash,upi,card,other,0,cash,counted_cash_minor,difference))
        return {"expected_cash_minor": cash, "counted_cash_minor": counted_cash_minor, "difference_minor": difference}


def seed_shop(db: Database, shop_name: str, initial_password: str) -> tuple[str, str]:
    with db.transaction() as c:
        existing = c.execute("SELECT id FROM shops LIMIT 1").fetchone()
        if existing: return existing[0], ""
        shop_id, owner_id, now = new_id(), new_id(), utc_now()
        c.execute("INSERT INTO shops VALUES(?,?,?,?)", (shop_id,shop_name,"UTC",now))
        c.execute("INSERT INTO users VALUES(?,?,?,?,?,?,?)", (owner_id,"owner","Owner","owner",hash_password(initial_password),1,now))
        return shop_id, owner_id
