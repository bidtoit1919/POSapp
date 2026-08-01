from __future__ import annotations

import csv
from pathlib import Path

from posdesk.data.database import Database


def export_sales_csv(db: Database, destination: Path, start_date: str, end_date: str, shop_id: str | None = None) -> int:
    """Export a stable, accounting-friendly sales view without exposing database files."""
    sql = """SELECT s.bill_number,s.business_date,s.sold_at,u.display_name cashier,
              COALESCE(c.name,'') customer,s.subtotal_minor,s.discount_minor,s.tax_minor,
              s.total_minor,p.method payment_method,p.amount_minor payment_minor
              FROM sales s JOIN users u ON u.id=s.cashier_id JOIN payments p ON p.sale_id=s.id
              LEFT JOIN customers c ON c.id=s.customer_id
              WHERE s.business_date BETWEEN ? AND ?"""
    values: list[str] = [start_date, end_date]
    if shop_id:
        sql += " AND s.shop_id=?"; values.append(shop_id)
    sql += " ORDER BY s.sold_at, s.bill_number"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with db.connect() as conn, destination.open("w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(["Bill Number","Business Date","Sold At (UTC)","Cashier","Customer","Subtotal (minor)","Discount (minor)","Tax (minor)","Total (minor)","Payment Method","Payment (minor)"])
        rows = conn.execute(sql, values).fetchall(); writer.writerows(rows)
    return len(rows)
