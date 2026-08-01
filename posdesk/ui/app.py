from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from posdesk.domain.services import CartLine, PosError, PosService


class PosApp(tk.Tk):
    def __init__(self, service: PosService, first_run_password: str = ""):
        super().__init__()
        self.service, self.first_run_password, self.cashier_id, self.cart, self.matches = service, first_run_password, None, [], []
        self.title("ShopPOS"); self.geometry("1000x650"); self.minsize(800, 500)
        self._show_login()

    def _clear(self) -> ttk.Frame:
        for child in self.winfo_children(): child.destroy()
        root = ttk.Frame(self, padding=24); root.pack(fill="both", expand=True)
        return root

    def _show_login(self) -> None:
        self.title("ShopPOS — Sign in")
        root = self._clear(); card = ttk.Frame(root, padding=28); card.place(relx=.5, rely=.5, anchor="center")
        ttk.Label(card, text="ShopPOS", font=("TkDefaultFont", 26, "bold")).pack(anchor="w")
        ttk.Label(card, text="Sign in to start billing.", font=("TkDefaultFont", 12)).pack(anchor="w", pady=(2, 18))
        if self.first_run_password:
            notice = ("Welcome — this is the first time ShopPOS has been opened.\n\n"
                      "Sign in with username: owner\n"
                      f"Temporary password: {self.first_run_password}\n\n"
                      "Write this down securely. Add your first product after signing in.")
            ttk.Label(card, text=notice, justify="left", wraplength=440).pack(anchor="w", pady=(0, 18))
        ttk.Label(card, text="Username").pack(anchor="w")
        self.username = ttk.Entry(card, width=36, font=("TkDefaultFont", 12)); self.username.pack(fill="x", pady=(2, 12)); self.username.insert(0, "owner")
        ttk.Label(card, text="Password").pack(anchor="w")
        self.password = ttk.Entry(card, width=36, show="●", font=("TkDefaultFont", 12)); self.password.pack(fill="x", pady=(2, 16)); self.password.bind("<Return>", lambda _: self._sign_in())
        ttk.Button(card, text="Sign in", command=self._sign_in).pack(anchor="e")
        self.password.focus_set()

    def _sign_in(self) -> None:
        user = self.service.authenticate(self.username.get(), self.password.get())
        if not user:
            messagebox.showerror("Sign in failed", "Check the username and password, then try again.")
            self.password.selection_range(0, "end"); self.password.focus_set(); return
        self.cashier_id, self.user = user["id"], user
        self.first_run_password = ""
        self._show_billing()

    def _show_billing(self) -> None:
        self.title("ShopPOS — Billing")
        root = self._clear()
        header = ttk.Frame(root); header.pack(fill="x")
        ttk.Label(header, text="Billing", font=("TkDefaultFont", 22, "bold")).pack(side="left")
        ttk.Label(header, text=f"Signed in: {self.user['display_name']}").pack(side="right")
        tools = ttk.Frame(root); tools.pack(fill="x", pady=(12, 4))
        ttk.Label(tools, text="Search or scan a product", font=("TkDefaultFont", 12)).pack(side="left")
        if self.user["role"] == "owner": ttk.Button(tools, text="+ Add product", command=self._add_product_dialog).pack(side="right")
        self.search = ttk.Entry(root, font=("TkDefaultFont", 14)); self.search.pack(fill="x", pady=(2,4)); self.search.bind("<KeyRelease>", self._search); self.search.bind("<Return>", lambda _: self._add_selected())
        self.products = tk.Listbox(root, height=8, font=("TkDefaultFont", 12)); self.products.pack(fill="x"); self.products.bind("<Double-Button-1>", lambda _: self._add_selected())
        self.hint = ttk.Label(root, text="Type a product name, SKU, or barcode above. Owners: select “Add product” to set up your first item.", foreground="#555")
        self.hint.pack(anchor="w", pady=(4, 0))
        ttk.Label(root, text="Current sale", font=("TkDefaultFont", 13, "bold")).pack(anchor="w", pady=(14, 2))
        self.cart_view = tk.Listbox(root, font=("TkDefaultFont", 13)); self.cart_view.pack(fill="both", expand=True)
        footer = ttk.Frame(root); footer.pack(fill="x", pady=(12, 0))
        self.total_label = ttk.Label(footer, text="Total: ₹0.00", font=("TkDefaultFont", 18, "bold")); self.total_label.pack(side="left")
        for method in ("cash", "upi", "card"):
            ttk.Button(footer, text=f"Pay {method.upper()}", command=lambda m=method: self._checkout(m)).pack(side="right", padx=4)
        ttk.Button(footer, text="Remove line", command=self._remove).pack(side="right", padx=12)
        self.search.focus_set()

    def _add_product_dialog(self) -> None:
        window = tk.Toplevel(self); window.title("Add product"); window.transient(self); window.grab_set(); window.resizable(False, False)
        form = ttk.Frame(window, padding=22); form.pack(fill="both", expand=True)
        ttk.Label(form, text="Add your first product", font=("TkDefaultFont", 16, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))
        fields: dict[str, ttk.Entry] = {}
        for row, (key, label, default) in enumerate((("name", "Product name", ""), ("sku", "SKU / item code", ""), ("price", "Selling price (₹)", "0.00"), ("quantity", "Opening quantity", "0")), 1):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=5)
            entry = ttk.Entry(form, width=30); entry.grid(row=row, column=1, pady=5); entry.insert(0, default); fields[key] = entry
        def save() -> None:
            try:
                price = round(float(fields["price"].get()) * 100)
                self.service.add_product(fields["name"].get(), fields["sku"].get(), price, quantity=int(fields["quantity"].get()))
            except (ValueError, PosError) as exc: messagebox.showerror("Cannot add product", str(exc), parent=window); return
            window.destroy(); self.search.delete(0, "end"); self._search(); self.search.focus_set()
        ttk.Button(form, text="Save product", command=save).grid(row=5, column=1, sticky="e", pady=(14, 0)); fields["name"].focus_set()

    def _search(self, _=None) -> None:
        self.matches = self.service.find_products(self.search.get()) if self.search.get().strip() else []
        self.products.delete(0, "end")
        for p in self.matches: self.products.insert("end", f"{p['name']}  [{p['sku']}]  Stock: {p['quantity']}  ₹{p['selling_price_minor']/100:.2f}")
        self.hint.config(text="Double-click a product or press Enter to add it to this sale." if self.matches else "No matching products. Owners: choose “Add product” to create one.")

    def _add_selected(self) -> None:
        selected = self.products.curselection()
        if not selected: return
        product = self.matches[selected[0]]
        for line in self.cart:
            if line.product_id == product["id"]: line.quantity += 1; break
        else: self.cart.append(CartLine(product["id"], 1))
        self._refresh_cart(); self.search.delete(0, "end"); self._search()

    def _refresh_cart(self) -> None:
        self.cart_view.delete(0, "end"); total = 0; products = {p["id"]: p for p in self.service.find_products("")}
        for line in self.cart:
            if p := products.get(line.product_id):
                total += p["selling_price_minor"] * line.quantity
                self.cart_view.insert("end", f"{p['name']} × {line.quantity}    ₹{p['selling_price_minor']*line.quantity/100:.2f}")
        self.total_label.config(text=f"Total: ₹{total/100:.2f}")

    def _remove(self) -> None:
        chosen = self.cart_view.curselection()
        if chosen: self.cart.pop(chosen[0]); self._refresh_cart()

    def _checkout(self, method: str) -> None:
        try:
            receipt = self.service.complete_sale(self.cashier_id, self.cart, method)
            messagebox.showinfo("Sale completed", f"Bill {receipt['bill_number']}\nTotal ₹{receipt['total_minor']/100:.2f}")
            self.cart.clear(); self._refresh_cart(); self.search.focus_set()
        except PosError as exc: messagebox.showerror("Cannot complete sale", str(exc))
