"""选择商品与数量，精确预览金额；计入后仍由记账表单保存支出。"""
import sqlite3
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, ttk

import customtkinter as ctk

from ledger import format_amount, parse_amount


BG, INK, MUTED = "#F5F6FA", "#232B42", "#8A91A4"
ACCENT, LINE, RED = "#6C5CE7", "#E9ECF3", "#DB6170"
FONT = "Microsoft YaHei UI"


def product_subtotal(product: sqlite3.Row, quantity_text: str) -> tuple[int, int]:
    value = quantity_text.strip()
    if not value.isascii() or not value.isdecimal():
        raise ValueError("数量请输入 1～999999 之间的正整数。")
    digits = value.lstrip("0")
    if not digits or len(digits) > 6:
        raise ValueError("数量请输入 1～999999 之间的正整数。")
    quantity = int(digits)
    subtotal = product["price_units"] * quantity
    subtotal = parse_amount(format_amount(subtotal).replace(",", ""))
    return quantity, subtotal


class ProductPicker(ctk.CTkToplevel):
    def __init__(self, master, products: list[sqlite3.Row], on_apply):
        super().__init__(master)
        self.withdraw()
        self.title("选择商品")
        self.geometry("640x500")
        self.minsize(520, 420)
        self.configure(fg_color=BG)
        self.products = {str(product["id"]): product for product in products}
        self.on_apply = on_apply
        self.quantity_var = tk.StringVar(self, "1")
        self.price_var = tk.StringVar(self, "")
        self.subtotal_var = tk.StringVar(self, "")
        self.error_var = tk.StringVar(self, "")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(self, text="选择商品", text_color=INK,
                     font=(FONT, 20, "bold")).grid(row=0, column=0, sticky="w", padx=22, pady=(18, 10))
        table = ctk.CTkFrame(self, fg_color="white", corner_radius=10)
        table.grid(row=1, column=0, sticky="nsew", padx=22)
        table.grid_columnconfigure(0, weight=1)
        table.grid_rowconfigure(0, weight=1)
        scale = self._get_window_scaling()
        self.table_font = tkfont.Font(self, family=FONT, size=-round(12 * scale))
        style = ttk.Style(self)
        style.configure("ProductPicker.Treeview", background="white", fieldbackground="white",
                         foreground=INK, rowheight=round(34 * scale), borderwidth=0, font=self.table_font)
        style.configure("ProductPicker.Treeview.Heading", background="#F7F8FB", foreground=MUTED,
                         font=self.table_font, padding=(round(6 * scale), round(7 * scale)))
        style.map("ProductPicker.Treeview", background=[("selected", "#F0EDFF")],
                  foreground=[("selected", ACCENT)])
        self.tree = ttk.Treeview(table, columns=("name", "price"), show="headings",
                                 selectmode="browse", height=6, style="ProductPicker.Treeview")
        self.tree.heading("name", text="商品名称", anchor="w")
        self.tree.heading("price", text="单价（元）", anchor="e")
        name_width = max(round(300 * scale), max(self.table_font.measure(row["name"]) for row in products) + round(24 * scale))
        price_width = max(round(130 * scale), max(self.table_font.measure(format_amount(row["price_units"])) for row in products) + round(24 * scale))
        self.tree.column("name", width=name_width, minwidth=name_width, stretch=False)
        self.tree.column("price", width=price_width, minwidth=price_width, stretch=False, anchor="e")
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=(10, 0))
        vertical = ctk.CTkScrollbar(table, command=self.tree.yview, width=12,
                                  button_color="#CBD1DF", button_hover_color="#B2BACC")
        vertical.grid(row=0, column=1, sticky="ns", padx=(2, 8), pady=(10, 0))
        horizontal = ctk.CTkScrollbar(table, command=self.tree.xview, orientation="horizontal", height=12,
                                    button_color="#CBD1DF", button_hover_color="#B2BACC")
        horizontal.grid(row=1, column=0, sticky="ew", padx=10, pady=(2, 8))
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        for product in products:
            self.tree.insert("", "end", iid=str(product["id"]),
                             values=(product["name"], format_amount(product["price_units"])))
        self.tree.selection_set(str(products[0]["id"]))
        self.tree.bind("<<TreeviewSelect>>", self._preview)

        details = ctk.CTkFrame(self, fg_color="white", corner_radius=10)
        details.grid(row=2, column=0, sticky="ew", padx=22, pady=(12, 0))
        details.grid_columnconfigure((0, 1, 2), weight=1)
        for column, title in enumerate(("数量（1～999999）", "选中单价", "商品小计")):
            ctk.CTkLabel(details, text=title, font=(FONT, 11), text_color=MUTED).grid(
                row=0, column=column, sticky="w", padx=14, pady=(8, 0))
        self.quantity_entry = ctk.CTkEntry(
            details, textvariable=self.quantity_var, width=140, height=34,
            font=(FONT, 13), fg_color="white", text_color=INK, border_color=LINE, corner_radius=8)
        self.quantity_entry.grid(row=1, column=0, sticky="ew", padx=14, pady=(2, 12))
        ctk.CTkLabel(details, textvariable=self.price_var, text="", font=(FONT, 13), text_color=INK).grid(
            row=1, column=1, sticky="w", padx=14, pady=(2, 12))
        ctk.CTkLabel(details, textvariable=self.subtotal_var, text="", font=(FONT, 15, "bold"), text_color=ACCENT).grid(
            row=1, column=2, sticky="w", padx=14, pady=(2, 12))
        ctk.CTkLabel(self, textvariable=self.error_var, text="", font=(FONT, 11), text_color=RED,
                     anchor="w", wraplength=590).grid(row=3, column=0, sticky="ew", padx=22, pady=(3, 0))
        ctk.CTkLabel(self, text="选择商品仅填入金额，仍需点击“保存支出”完成记账。",
                     font=(FONT, 11), text_color=MUTED, anchor="w").grid(
                         row=4, column=0, sticky="w", padx=22, pady=(0, 10))
        actions = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        actions.grid(row=5, column=0, sticky="ew", padx=22, pady=(0, 18))
        actions.grid_columnconfigure(0, weight=1)
        self.cancel_button = ctk.CTkButton(
            actions, text="取消", width=68, height=34, font=(FONT, 12), corner_radius=8,
            fg_color="#F1F3F8", text_color=INK, hover_color="#E7EAF2", command=self.destroy)
        self.cancel_button.grid(row=0, column=0, sticky="w")
        self.replace_button = ctk.CTkButton(
            actions, text="计入金额", width=112, height=34, font=(FONT, 12), corner_radius=8,
            fg_color=ACCENT, hover_color="#5A49D1", command=lambda: self._apply(False))
        self.replace_button.grid(row=0, column=1, padx=(0, 8))
        self.add_button = ctk.CTkButton(
            actions, text="累加到金额", width=120, height=34, font=(FONT, 12), corner_radius=8,
            fg_color=ACCENT, hover_color="#5A49D1", command=lambda: self._apply(True))
        self.add_button.grid(row=0, column=2)
        self._quantity_trace = self.quantity_var.trace_add("write", self._preview)
        self._preview()
        self.bind("<Escape>", lambda event: self.destroy())
        self._map_binding = self.bind("<Map>", self._mapped, add="+")
        self.deiconify()

    def _mapped(self, event):
        if event.widget is self:
            self.unbind("<Map>", self._map_binding)
            self.transient(self.master.winfo_toplevel())
            self.grab_set()
            self.quantity_entry.focus_set()

    def _selected_product(self):
        selected = self.tree.selection()
        if not selected:
            raise ValueError("请选择一个商品。")
        return self.products[selected[0]]

    def _preview(self, *args):
        self.price_var.set("未选择")
        try:
            product = self._selected_product()
            self.price_var.set(f"¥ {format_amount(product['price_units'])}")
            _, subtotal = product_subtotal(product, self.quantity_var.get())
        except ValueError as error:
            self.subtotal_var.set("无法计算")
            self.error_var.set(str(error))
            return
        self.subtotal_var.set(f"¥ {format_amount(subtotal)}")
        self.error_var.set("")

    def _apply(self, add):
        try:
            product = self._selected_product()
            quantity, _ = product_subtotal(product, self.quantity_var.get())
            self.on_apply(product, quantity, add)
        except ValueError as error:
            self.error_var.set(str(error))
            messagebox.showwarning("无法计入金额", str(error), parent=self)
            return
        self.destroy()

    def destroy(self):
        self.quantity_var.trace_remove("write", self._quantity_trace)
        # 与日期弹窗相同，销毁 Tcl command 前释放本窗口及子控件拥有的 after。
        widgets, owners = [self], {}
        while widgets:
            widget = widgets.pop()
            owners.update((command, widget) for command in widget._tclCommands or ())
            widgets.extend(widget.winfo_children())
        for callback_id in self.tk.call("after", "info"):
            script, _ = self.tk.call("after", "info", callback_id)
            command = script.split()[0]
            if command in owners:
                owners[command].after_cancel(callback_id)
        super().destroy()
