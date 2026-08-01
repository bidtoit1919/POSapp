from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import tkinter as tk
from tkinter import messagebox, ttk

from posdesk.domain.services import CartLine, PosError, PosService


def money(minor: int) -> str: return f"₹{minor / 100:,.2f}"


def parse_money(value: str) -> int:
    try:
        amount = Decimal(value.strip()).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation as exc: raise PosError("Enter a valid price, for example 49.50") from exc
    if amount < 0: raise PosError("Price cannot be negative")
    return int(amount * 100)


class PosApp(tk.Tk):
    def __init__(self, service: PosService, first_run_password: str = ""):
        super().__init__()
        self.service, self.first_run_password, self.cashier_id = service, first_run_password, None
        self.cart: list[CartLine] = []; self.cart_products: dict[str, dict] = {}; self.matches: list[dict] = []
        self.title("ShopPOS"); self.geometry("1180x720"); self.minsize(940, 600)
        style = ttk.Style(self); style.configure("Treeview", rowheight=30, font=("TkDefaultFont", 11)); style.configure("Treeview.Heading", font=("TkDefaultFont", 10, "bold"))
        self._show_login()

    def _clear(self) -> ttk.Frame:
        for child in self.winfo_children(): child.destroy()
        root = ttk.Frame(self, padding=18); root.pack(fill="both", expand=True); return root

    def _show_login(self) -> None:
        self.title("ShopPOS — Sign in"); root = self._clear(); card = ttk.Frame(root, padding=30); card.place(relx=.5, rely=.5, anchor="center")
        ttk.Label(card, text="ShopPOS", font=("TkDefaultFont", 28, "bold")).pack(anchor="w")
        ttk.Label(card, text="Sign in to start billing.", font=("TkDefaultFont", 12)).pack(anchor="w", pady=(2, 18))
        if self.first_run_password:
            ttk.Label(card, text=f"First setup\n\nUsername: owner\nTemporary password: {self.first_run_password}\n\nSave this password, then sign in and add products in Inventory.", justify="left", wraplength=440).pack(anchor="w", pady=(0, 18))
        ttk.Label(card, text="Username").pack(anchor="w"); self.username = ttk.Entry(card, width=38, font=("TkDefaultFont", 12)); self.username.pack(fill="x", pady=(2, 12)); self.username.insert(0, "owner")
        ttk.Label(card, text="Password").pack(anchor="w"); self.password = ttk.Entry(card, width=38, show="●", font=("TkDefaultFont", 12)); self.password.pack(fill="x", pady=(2, 16)); self.password.bind("<Return>", lambda _event: self._sign_in())
        ttk.Button(card, text="Sign in", command=self._sign_in).pack(anchor="e")
        ttk.Label(card, text="Forgot the password? The technical owner can run the local password-recovery utility.", foreground="#555", wraplength=430).pack(anchor="w", pady=(16, 0)); self.password.focus_set()

    def _sign_in(self) -> None:
        user = self.service.authenticate(self.username.get(), self.password.get())
        if not user:
            messagebox.showerror("Sign in failed", "Check the username and password, then try again."); self.password.selection_range(0, "end"); self.password.focus_set(); return
        self.cashier_id, self.user, self.first_run_password = user["id"], user, ""; self._show_workspace()

    def _show_workspace(self) -> None:
        self.title("ShopPOS"); root = self._clear(); top = ttk.Frame(root); top.pack(fill="x")
        ttk.Label(top, text="ShopPOS", font=("TkDefaultFont", 20, "bold")).pack(side="left")
        ttk.Label(top, text=f"Signed in: {self.user['display_name']} ({self.user['role']})").pack(side="right")
        notebook = ttk.Notebook(root); notebook.pack(fill="both", expand=True, pady=(14, 0))
        billing = ttk.Frame(notebook, padding=14); notebook.add(billing, text="  Billing  "); self._build_billing(billing)
        if self.user["role"] == "owner":
            inventory = ttk.Frame(notebook, padding=14); notebook.add(inventory, text="  Inventory  "); self._build_inventory(inventory)

    def _tree(self, parent, columns: tuple[str, ...], headings: tuple[str, ...], widths: tuple[int, ...]) -> ttk.Treeview:
        tree = ttk.Treeview(parent, columns=columns, show="headings", selectmode="browse")
        for key, heading, width in zip(columns, headings, widths): tree.heading(key, text=heading); tree.column(key, width=width, anchor="e" if key in {"stock", "price", "total", "qty", "low"} else "w")
        return tree

    def _build_billing(self, root: ttk.Frame) -> None:
        ttk.Label(root, text="Scan barcode or search", font=("TkDefaultFont", 13, "bold")).pack(anchor="w")
        search_row = ttk.Frame(root); search_row.pack(fill="x", pady=(4, 8))
        self.search = ttk.Entry(search_row, font=("TkDefaultFont", 15)); self.search.pack(side="left", fill="x", expand=True); self.search.bind("<KeyRelease>", self._search); self.search.bind("<Return>", self._scan_or_add)
        ttk.Button(search_row, text="Add selected", command=self._add_selected).pack(side="left", padx=(8, 0))
        ttk.Label(root, text="A USB barcode scanner works like a keyboard: scan the item and it is added automatically.", foreground="#555").pack(anchor="w", pady=(0, 5))
        self.results = self._tree(root, ("name", "sku", "barcode", "stock", "price"), ("Product", "SKU", "Barcode", "Stock", "Price"), (300, 150, 180, 80, 110)); self.results.pack(fill="x"); self.results.bind("<Double-1>", lambda _event: self._add_selected())
        ttk.Label(root, text="Current sale", font=("TkDefaultFont", 13, "bold")).pack(anchor="w", pady=(16, 4))
        self.cart_view = self._tree(root, ("name", "sku", "price", "qty", "total"), ("Product", "SKU", "Unit price", "Quantity", "Line total"), (390, 160, 130, 110, 150)); self.cart_view.pack(fill="both", expand=True); self.cart_view.bind("<<TreeviewSelect>>", self._cart_selected)
        cart_tools = ttk.Frame(root); cart_tools.pack(fill="x", pady=8)
        ttk.Label(cart_tools, text="Selected quantity:").pack(side="left"); self.quantity = tk.StringVar(value="1"); ttk.Spinbox(cart_tools, from_=1, to=9999, textvariable=self.quantity, width=8).pack(side="left", padx=6)
        ttk.Button(cart_tools, text="Update quantity", command=self._update_quantity).pack(side="left"); ttk.Button(cart_tools, text="Remove item", command=self._remove).pack(side="left", padx=8)
        self.total_label = ttk.Label(cart_tools, text="Total: ₹0.00", font=("TkDefaultFont", 18, "bold")); self.total_label.pack(side="right")
        pay = ttk.Frame(root); pay.pack(fill="x")
        ttk.Label(pay, text="Complete sale:", font=("TkDefaultFont", 12, "bold")).pack(side="left")
        for method in ("cash", "upi", "card"):
            ttk.Button(pay, text=f"Pay {method.upper()}", command=lambda m=method: self._checkout(m)).pack(side="right", padx=4)
        self.search.focus_set()

    def _search(self, _event=None) -> None:
        query = self.search.get().strip(); self.matches = self.service.find_products(query) if query else []
        self.results.delete(*self.results.get_children())
        for product in self.matches: self.results.insert("", "end", iid=product["id"], values=(product["name"], product["sku"], product["barcode"] or "", product["quantity"], money(product["selling_price_minor"])))

    def _scan_or_add(self, _event=None) -> None:
        code = self.search.get().strip(); product = self.service.find_product_by_code(code) if code else None
        if product: self._add_product(product)
        elif len(self.matches) == 1: self._add_product(self.matches[0])
        elif code: messagebox.showinfo("Product not found", f"No product matches “{code}”. Search by name or add it in Inventory.")

    def _add_selected(self) -> None:
        selected = self.results.selection()
        if selected:
            product = next((p for p in self.matches if p["id"] == selected[0]), None)
            if product: self._add_product(product)

    def _add_product(self, product: dict) -> None:
        line = next((line for line in self.cart if line.product_id == product["id"]), None)
        if line: line.quantity += 1
        else: self.cart.append(CartLine(product["id"], 1))
        self.cart_products[product["id"]] = product; self.search.delete(0, "end"); self._search(); self._refresh_cart(); self.search.focus_set()

    def _cart_selected(self, _event=None) -> None:
        selected = self.cart_view.selection()
        if selected:
            line = next((line for line in self.cart if line.product_id == selected[0]), None)
            if line: self.quantity.set(str(line.quantity))

    def _update_quantity(self) -> None:
        selected = self.cart_view.selection()
        try: quantity = int(self.quantity.get())
        except ValueError: messagebox.showerror("Invalid quantity", "Enter a whole number greater than zero."); return
        if not selected or quantity < 1: messagebox.showerror("Invalid quantity", "Select an item and enter a whole number greater than zero."); return
        for line in self.cart:
            if line.product_id == selected[0]: line.quantity = quantity; break
        self._refresh_cart()

    def _refresh_cart(self) -> None:
        self.cart_view.delete(*self.cart_view.get_children()); total = 0
        for line in self.cart:
            product = self.cart_products[line.product_id]; base = product["selling_price_minor"] * line.quantity; tax = (base * product["tax_bps"] + 5000) // 10000; line_total = base + tax; total += line_total
            self.cart_view.insert("", "end", iid=line.product_id, values=(product["name"], product["sku"], money(product["selling_price_minor"]), line.quantity, money(line_total)))
        self.total_label.config(text=f"Total: {money(total)}")

    def _remove(self) -> None:
        selected = self.cart_view.selection()
        if selected: self.cart = [line for line in self.cart if line.product_id != selected[0]]; self.cart_products.pop(selected[0], None); self._refresh_cart()

    def _checkout(self, method: str) -> None:
        try:
            receipt = self.service.complete_sale(self.cashier_id, self.cart, method)
            messagebox.showinfo("Sale completed", f"Bill {receipt['bill_number']}\nTotal {money(receipt['total_minor'])}")
            self.cart.clear(); self.cart_products.clear(); self._refresh_cart(); self.search.focus_set(); self._refresh_inventory()
        except PosError as exc: messagebox.showerror("Cannot complete sale", str(exc))

    def _build_inventory(self, root: ttk.Frame) -> None:
        top = ttk.Frame(root); top.pack(fill="x"); ttk.Label(top, text="Inventory management", font=("TkDefaultFont", 15, "bold")).pack(side="left")
        ttk.Button(top, text="+ Add product", command=lambda: self._product_dialog()).pack(side="right")
        ttk.Label(root, text="Search product, SKU, or barcode").pack(anchor="w", pady=(14, 2)); self.inventory_search = ttk.Entry(root, font=("TkDefaultFont", 12)); self.inventory_search.pack(fill="x"); self.inventory_search.bind("<KeyRelease>", lambda _event: self._refresh_inventory())
        self.inventory_view = self._tree(root, ("name", "sku", "barcode", "stock", "price", "low"), ("Product", "SKU", "Barcode", "On hand", "Selling price", "Low-stock at"), (290, 150, 170, 100, 130, 110)); self.inventory_view.pack(fill="both", expand=True, pady=8); self.inventory_view.tag_configure("low", foreground="#b00020"); self.inventory_view.bind("<Double-1>", lambda _event: self._edit_selected_product())
        bottom = ttk.Frame(root); bottom.pack(fill="x"); ttk.Button(bottom, text="Edit product", command=self._edit_selected_product).pack(side="left"); ttk.Button(bottom, text="Adjust stock", command=self._stock_adjust_dialog).pack(side="left", padx=8); ttk.Label(bottom, text="Tip: double-click a row to edit product details.", foreground="#555").pack(side="right")
        self._refresh_inventory()

    def _refresh_inventory(self) -> None:
        if not hasattr(self, "inventory_view"): return
        rows = self.service.list_inventory(self.inventory_search.get() if hasattr(self, "inventory_search") else "")
        self.inventory_rows = {row["id"]: row for row in rows}; self.inventory_view.delete(*self.inventory_view.get_children())
        for row in rows:
            tags = ("low",) if row["quantity"] <= row["low_stock_threshold"] else ()
            self.inventory_view.insert("", "end", iid=row["id"], values=(row["name"], row["sku"], row["barcode"] or "", row["quantity"], money(row["selling_price_minor"]), row["low_stock_threshold"]), tags=tags)

    def _selected_inventory(self) -> dict | None:
        selection = self.inventory_view.selection()
        if not selection: messagebox.showinfo("Select a product", "Choose a product from the inventory table first."); return None
        return self.inventory_rows[selection[0]]

    def _product_dialog(self, product: dict | None = None) -> None:
        window = tk.Toplevel(self); window.title("Add product" if product is None else "Edit product"); window.transient(self); window.grab_set(); window.resizable(False, False)
        form = ttk.Frame(window, padding=24); form.pack(fill="both", expand=True); ttk.Label(form, text=window.title(), font=("TkDefaultFont", 16, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 14))
        specs = (("name", "Product name", ""), ("sku", "SKU / item code", ""), ("barcode", "Barcode (optional)", ""), ("selling", "Selling price (₹)", "0.00"), ("buying", "Buying price (₹)", "0.00"), ("tax", "Tax (%)", "0"), ("low", "Low-stock warning at", "0"))
        if product is None: specs += (("opening", "Opening quantity", "0"),)
        entries: dict[str, ttk.Entry] = {}
        for row, (key, label, default) in enumerate(specs, 1):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", padx=(0, 16), pady=4); entry = ttk.Entry(form, width=32); entry.grid(row=row, column=1, pady=4); value = default
            if product:
                values = {"name": product["name"], "sku": product["sku"], "barcode": product["barcode"] or "", "selling": f"{product['selling_price_minor']/100:.2f}", "buying": f"{product['buying_price_minor']/100:.2f}", "tax": f"{product['tax_bps']/100:.2f}", "low": str(product["low_stock_threshold"])}; value = values[key]
            entry.insert(0, value); entries[key] = entry
        def save() -> None:
            try:
                tax_bps = int((Decimal(entries["tax"].get()) * 100).quantize(Decimal("1"))); low = int(entries["low"].get())
                if product is None: self.service.add_product(entries["name"].get(), entries["sku"].get(), parse_money(entries["selling"].get()), quantity=int(entries["opening"].get()), barcode=entries["barcode"].get(), buying_price_minor=parse_money(entries["buying"].get()), tax_bps=tax_bps, low_stock_threshold=low)
                else: self.service.update_product(self.cashier_id, product["id"], name=entries["name"].get(), sku=entries["sku"].get(), barcode=entries["barcode"].get(), selling_price_minor=parse_money(entries["selling"].get()), buying_price_minor=parse_money(entries["buying"].get()), tax_bps=tax_bps, low_stock_threshold=low)
            except (ValueError, InvalidOperation, PosError) as exc: messagebox.showerror("Cannot save product", str(exc), parent=window); return
            window.destroy(); self._refresh_inventory()
        ttk.Button(form, text="Save product", command=save).grid(row=len(specs)+1, column=1, sticky="e", pady=(16, 0)); entries["name"].focus_set()

    def _edit_selected_product(self) -> None:
        product = self._selected_inventory()
        if product: self._product_dialog(product)

    def _stock_adjust_dialog(self) -> None:
        product = self._selected_inventory()
        if not product: return
        window = tk.Toplevel(self); window.title("Adjust stock"); window.transient(self); window.grab_set(); form = ttk.Frame(window, padding=24); form.pack()
        ttk.Label(form, text=f"Adjust stock — {product['name']}", font=("TkDefaultFont", 15, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12)); ttk.Label(form, text=f"Current quantity: {product['quantity']}").grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 12))
        ttk.Label(form, text="Change (+ received / − removed)").grid(row=2, column=0, sticky="w", pady=4); delta = ttk.Entry(form, width=24); delta.grid(row=2, column=1, pady=4); delta.insert(0, "0")
        ttk.Label(form, text="Reason").grid(row=3, column=0, sticky="w", pady=4); reason = ttk.Combobox(form, values=("intake", "correction", "damage", "expiry"), state="readonly", width=21); reason.grid(row=3, column=1, pady=4); reason.set("correction")
        ttk.Label(form, text="Note").grid(row=4, column=0, sticky="w", pady=4); note = ttk.Entry(form, width=24); note.grid(row=4, column=1, pady=4)
        def save() -> None:
            try: self.service.adjust_stock(self.cashier_id, product["id"], int(delta.get()), reason.get(), note.get())
            except (ValueError, PosError) as exc: messagebox.showerror("Cannot adjust stock", str(exc), parent=window); return
            window.destroy(); self._refresh_inventory()
        ttk.Button(form, text="Save adjustment", command=save).grid(row=5, column=1, sticky="e", pady=(16, 0)); delta.focus_set()
