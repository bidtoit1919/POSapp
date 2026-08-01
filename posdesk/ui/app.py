from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from posdesk.domain.services import CartLine, PosError, PosService

class PosApp(tk.Tk):
    def __init__(self, service: PosService, cashier_id: str):
        super().__init__(); self.service, self.cashier_id, self.cart = service, cashier_id, []
        self.title("ShopPOS — Billing"); self.geometry("1000x650"); self.minsize(800, 500)
        self._build(); self.search.focus_set()
    def _build(self):
        root = ttk.Frame(self, padding=16); root.pack(fill="both", expand=True)
        ttk.Label(root, text="Billing", font=("TkDefaultFont", 20, "bold")).pack(anchor="w")
        self.search = ttk.Entry(root, font=("TkDefaultFont", 14)); self.search.pack(fill="x", pady=(12,4)); self.search.bind("<KeyRelease>", self._search); self.search.bind("<Return>", lambda _: self._add_selected())
        self.products = tk.Listbox(root, height=8, font=("TkDefaultFont", 12)); self.products.pack(fill="x"); self.products.bind("<Double-Button-1>", lambda _: self._add_selected())
        self.cart_view = tk.Listbox(root, font=("TkDefaultFont", 13)); self.cart_view.pack(fill="both", expand=True, pady=12)
        footer = ttk.Frame(root); footer.pack(fill="x")
        self.total_label = ttk.Label(footer, text="Total: ₹0.00", font=("TkDefaultFont", 18, "bold")); self.total_label.pack(side="left")
        for method in ("cash", "upi", "card"):
            ttk.Button(footer, text=f"Pay {method.upper()}", command=lambda m=method: self._checkout(m)).pack(side="right", padx=4)
        ttk.Button(footer, text="Remove line", command=self._remove).pack(side="right", padx=12)
    def _search(self, _=None):
        self.matches = self.service.find_products(self.search.get()) if self.search.get().strip() else []
        self.products.delete(0, "end")
        for p in self.matches: self.products.insert("end", f"{p['name']}  [{p['sku']}]  Stock: {p['quantity']}  ₹{p['selling_price_minor']/100:.2f}")
    def _add_selected(self):
        selected = self.products.curselection()
        if not selected: return
        product = self.matches[selected[0]]
        for line in self.cart:
            if line.product_id == product['id']: line.quantity += 1; break
        else: self.cart.append(CartLine(product['id'], 1))
        self._refresh_cart(); self.search.delete(0, "end"); self._search()
    def _refresh_cart(self):
        self.cart_view.delete(0, "end"); total = 0
        for line in self.cart:
            p = next((p for p in self.service.find_products("") if p['id'] == line.product_id), None)
            if p: total += p['selling_price_minor'] * line.quantity; self.cart_view.insert("end", f"{p['name']} × {line.quantity}    ₹{p['selling_price_minor']*line.quantity/100:.2f}")
        self.total_label.config(text=f"Total: ₹{total/100:.2f}")
    def _remove(self):
        chosen = self.cart_view.curselection()
        if chosen: self.cart.pop(chosen[0]); self._refresh_cart()
    def _checkout(self, method: str):
        try:
            receipt = self.service.complete_sale(self.cashier_id, self.cart, method)
            messagebox.showinfo("Sale completed", f"Bill {receipt['bill_number']}\nTotal ₹{receipt['total_minor']/100:.2f}")
            self.cart.clear(); self._refresh_cart(); self.search.focus_set()
        except PosError as exc: messagebox.showerror("Cannot complete sale", str(exc))
