"""Windows 本地记账：分类、日历、统计、预算和备份。"""
import calendar
import ctypes
import logging
import sys
import tkinter as tk
import tkinter.font as tkfont
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk
from calendar_widget import CalendarDateEntry
from ledger import Ledger, format_amount, parse_amount, parse_day
from product_picker import ProductPicker, product_subtotal
from year_calendar import YearExpenseCalendar

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LOGGER = logging.getLogger("ledger_app")
BG, INK, MUTED = "#F5F6FA", "#232B42", "#8A91A4"
ACCENT, LINE, PALE = "#6C5CE7", "#E9ECF3", "#F0EDFF"
GREEN, RED, FONT = "#21A179", "#DB6170", "Microsoft YaHei UI"
ctk.set_appearance_mode("light")


def label(parent, text="", size=13, color=INK, bold=False, variable=None, **kwargs):
    kwargs.setdefault("height", max(20, size + 7))
    return ctk.CTkLabel(parent, text=text, textvariable=variable, text_color=color,
        font=(FONT, size, "bold" if bold else "normal"), **kwargs)


def button(parent, text, command, width=80, primary=False):
    return ctk.CTkButton(parent, text=text, command=command, width=width, height=34,
        corner_radius=8, font=(FONT, 12), fg_color=ACCENT if primary else "#F1F3F8",
        text_color="white" if primary else INK,
        hover_color="#5A49D1" if primary else "#E7EAF2")


def entry(parent, variable, width=140, height=34, size=13):
    return ctk.CTkEntry(parent, textvariable=variable, width=width, height=height,
        corner_radius=8, border_width=1, border_color=LINE,
        fg_color="white", text_color=INK, font=(FONT, size))


def combo(parent, variable, values, width=125, command=None, editable=False):
    return ctk.CTkComboBox(parent, variable=variable, values=list(values), width=width,
        height=34, corner_radius=8, border_width=1, border_color=LINE,
        button_color="#ECEEF5", button_hover_color="#DFE3EE", dropdown_fg_color="white",
        dropdown_hover_color=PALE, text_color=INK, dropdown_text_color=INK,
        font=(FONT, 12), dropdown_font=(FONT, 12), command=command,
        state="normal" if editable else "readonly")


class LedgerApp(ctk.CTk):
    def __init__(self, ledger: Ledger):
        super().__init__()
        self.ledger = ledger
        self.editing_id = None
        self.product_editing_id = None
        self.product_picker = None
        self.product_note_draft = None
        self.entries = {}
        self.displayed_day = date.today().isoformat()
        self.sort_key, self.sort_reverse = "day", True
        self.chart_data = {"by_day": {}, "by_category": [], "total_units": 0, "count": 0}
        self.chart_month = date.today().replace(day=1)
        self.calendar_year = date.today().year
        self.calendar_selected_day = date.today().isoformat()
        self.title("日常记账")
        self.geometry("1280x800+40+30")
        self.minsize(1120, 740)
        self.configure(fg_color=BG)
        today = date.today().isoformat()
        variables = {
            "entry_day_var": today, "view_day_var": today, "amount_var": "", "note_var": "",
            "category_var": "未分类", "payment_var": "未指定", "period_var": "本月",
            "filter_category_var": "全部分类", "filter_payment_var": "全部方式", "keyword_var": "",
            "range_start_var": today[:8] + "01", "range_end_var": today,
            "total_var": "¥ 0.00", "count_var": "0", "today_total_var": "¥ 0.00",
            "month_total_var": "¥ 0.00", "day_label_var": "筛选支出", "form_title_var": "记一笔",
            "status_var": "账本已就绪", "page_title_var": "账本明细",
            "report_day_var": today, "report_total_var": "¥ 0.00", "report_count_var": "0 笔",
            "report_average_var": "¥ 0.00", "budget_day_var": today, "budget_amount_var": "",
            "budget_total_var": "未设置", "budget_spent_var": "¥ 0.00",
            "budget_remaining_var": "选择月份，设置你的月预算", "storage_var": "",
            "calendar_year_var": str(self.calendar_year), "calendar_total_var": "¥ 0.00",
            "calendar_count_var": "0 笔 · 0 个记账日",
            "product_name_var": "", "product_price_var": "",
            "product_form_title_var": "添加商品", "product_count_var": "0 个商品",
        }
        for name, value in variables.items():
            setattr(self, name, tk.StringVar(self, value=value))
        self._build_style()
        self._build_window()
        self.apply_filters()
        self.show_page("账本明细", refresh=False)

    def _build_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        scale = self._get_window_scaling()
        self.table_font = tkfont.Font(family=FONT, size=-round(12 * scale))
        style.configure("Ledger.Treeview", background="white", fieldbackground="white",
            foreground=INK, rowheight=round(38 * scale), borderwidth=0, font=self.table_font,
            bordercolor=LINE, lightcolor="white", darkcolor="white", relief="flat")
        style.configure("Ledger.Treeview.Heading", background="#F7F8FB", foreground=MUTED,
            padding=(round(8 * scale), round(10 * scale)), relief="flat", font=self.table_font)
        style.map("Ledger.Treeview", background=[("selected", PALE)], foreground=[("selected", ACCENT)])

    def _build_window(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        sidebar = ctk.CTkFrame(self, width=176, corner_radius=0, fg_color="white")
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)
        navigation = ("账本明细", "支出日历", "商品管理", "统计分析", "预算管理", "数据备份")
        spacer_row = len(navigation) + 3
        sidebar.grid_rowconfigure(spacer_row, weight=1)
        logo = ctk.CTkFrame(sidebar, fg_color=ACCENT, corner_radius=12, width=42, height=42)
        logo.grid(row=0, column=0, pady=(28, 10))
        logo.grid_propagate(False)
        label(logo, "记", 22, "white", True).place(relx=.5, rely=.5, anchor="center")
        label(sidebar, "日常记账", 19, INK, True).grid(row=1, column=0)
        label(sidebar, "把生活，记清楚", 11, MUTED).grid(row=2, column=0, pady=(2, 30))
        self.nav_buttons = {}
        for index, name in enumerate(navigation):
            control = ctk.CTkButton(sidebar, text=name, anchor="w", width=144, height=42,
                corner_radius=9, font=(FONT, 13), fg_color="white", hover_color="#F5F3FF",
                text_color=MUTED, command=lambda selected=name: self.show_page(selected))
            control.grid(row=index + 3, column=0, padx=16, pady=4, sticky="ew")
            self.nav_buttons[name] = control
        label(sidebar, "●  本地保存", 11, GREEN).grid(row=spacer_row + 1, column=0, pady=(8, 2))
        label(sidebar, "你的账本，由你保管", 10, MUTED).grid(row=spacer_row + 2, column=0, pady=(0, 22))
        shell = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        shell.grid(row=0, column=1, sticky="nsew", padx=24, pady=20)
        shell.grid_columnconfigure(0, weight=1)
        shell.grid_rowconfigure(2, weight=1)
        header = ctk.CTkFrame(shell, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        header.grid_columnconfigure(0, weight=1)
        label(header, variable=self.page_title_var, size=23, bold=True, anchor="w").grid(row=0, column=0, sticky="w")
        label(header, "让每一笔支出，都有迹可循。", 12, MUTED, anchor="w").grid(row=1, column=0, sticky="w", pady=(2, 0))
        button(header, "导出 CSV", self.export_current, 98).grid(row=0, column=1, rowspan=2, padx=(0, 10))
        button(header, "+  记一笔", self.focus_form, 110, True).grid(row=0, column=2, rowspan=2)
        overview = ctk.CTkFrame(shell, fg_color="transparent")
        self.overview = overview
        overview.grid(row=1, column=0, sticky="ew", pady=(0, 18))
        overview.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="overview")
        cards = (("今日支出", self.today_total_var, "按今天的消费日期", INK),
            ("本月支出", self.month_total_var, "本月全部记录", INK),
            ("筛选支出", self.total_var, "当前明细列表的合计", ACCENT),
            ("筛选笔数", self.count_var, "当前列表记录数", INK))
        for index, (title, variable, caption, color) in enumerate(cards):
            card = ctk.CTkFrame(overview, fg_color="white", corner_radius=12, border_width=1, border_color=LINE)
            card.grid(row=0, column=index, sticky="ew", padx=(0 if index == 0 else 10, 0))
            label(card, title, 12, MUTED).pack(anchor="w", padx=18, pady=(13, 0))
            label(card, variable=variable, size=23, color=color, bold=True).pack(anchor="w", padx=18)
            label(card, caption, 10, MUTED).pack(anchor="w", padx=18, pady=(0, 13))
        self.page_container = ctk.CTkFrame(shell, fg_color="transparent")
        self.page_container.grid(row=2, column=0, sticky="nsew")
        self.page_container.grid_columnconfigure(0, weight=1)
        self.page_container.grid_rowconfigure(0, weight=1)
        self.pages = {}
        for name in self.nav_buttons:
            page = ctk.CTkFrame(self.page_container, fg_color="transparent")
            page.grid(row=0, column=0, sticky="nsew")
            self.pages[name] = page
        self._build_ledger_page(self.pages["账本明细"])
        self._build_calendar_page(self.pages["支出日历"])
        self._build_products_page(self.pages["商品管理"])
        self._build_reports_page(self.pages["统计分析"])
        self._build_budget_page(self.pages["预算管理"])
        self._build_backup_page(self.pages["数据备份"])
        footer = ctk.CTkFrame(shell, fg_color="transparent", height=24)
        footer.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        label(footer, variable=self.status_var, size=11, color=MUTED, anchor="w").pack(side="left")
        label(footer, "人民币 CNY  ·  本地账本", 10, MUTED).pack(side="right")

    def _build_ledger_page(self, page):
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(0, weight=1)
        records = ctk.CTkFrame(page, fg_color="white", corner_radius=12, border_width=1, border_color=LINE)
        records.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        records.grid_columnconfigure(0, weight=1)
        records.grid_rowconfigure(4, weight=1)
        toolbar = ctk.CTkFrame(records, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 12))
        label(toolbar, "流水明细", 15, INK, True).pack(side="left")
        self.delete_button = button(toolbar, "删除", self.delete_selected, 56)
        self.delete_button.configure(text_color=RED)
        self.delete_button.pack(side="right")
        self.edit_button = button(toolbar, "修改", self.edit_selected, 56)
        self.edit_button.pack(side="right", padx=(0, 8))
        period = ctk.CTkFrame(records, fg_color="transparent")
        period.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 10))
        ctk.CTkSegmentedButton(period, values=["当天", "本月", "全部", "自定义"],
            variable=self.period_var, command=lambda value: self.apply_filters(), font=(FONT, 12),
            height=33, corner_radius=7, fg_color="#F0F2F7", unselected_color="#F0F2F7",
            unselected_hover_color="#E7E9F2", selected_color=ACCENT,
            selected_hover_color="#5A49D1", text_color=INK).pack(side="left")
        self.view_day_entry = CalendarDateEntry(period, self.view_day_var, command=self.apply_filters, width=154)
        self.view_day_entry.pack(side="right")
        filters = ctk.CTkFrame(records, fg_color="transparent")
        filters.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 12))
        filters.grid_columnconfigure(3, weight=1)
        self.filter_category = combo(filters, self.filter_category_var, ["全部分类", *self.ledger.categories()],
            112, lambda value: self.apply_filters())
        self.filter_category.grid(row=0, column=0, padx=(0, 7))
        self.filter_payment = combo(filters, self.filter_payment_var, ["全部方式", *self.ledger.payments()],
            106, lambda value: self.apply_filters())
        self.filter_payment.grid(row=0, column=1, padx=(0, 7))
        label(filters, "搜索", 11, MUTED).grid(row=0, column=2, padx=(2, 7))
        self.search_entry = entry(filters, self.keyword_var, 110)
        self.search_entry.grid(row=0, column=3, sticky="ew", padx=(0, 7))
        self.search_entry.bind("<Return>", lambda event: self.apply_filters())
        self.query_button = button(filters, "筛选", self.apply_filters, 52)
        self.query_button.grid(row=0, column=4)
        self.range_frame = ctk.CTkFrame(records, fg_color="transparent")
        self.range_frame.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 10))
        label(self.range_frame, "起止日期", 11, MUTED).pack(side="left", padx=(0, 8))
        CalendarDateEntry(self.range_frame, self.range_start_var, width=151).pack(side="left")
        label(self.range_frame, "—", 12, MUTED).pack(side="left", padx=6)
        CalendarDateEntry(self.range_frame, self.range_end_var, width=151).pack(side="left")
        self.range_frame.grid_remove()
        table = ctk.CTkFrame(records, fg_color="white", corner_radius=0)
        table.grid(row=4, column=0, sticky="nsew", padx=16)
        table.grid_columnconfigure(0, weight=1)
        table.grid_rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(table, columns=("day", "category", "payment", "amount_units", "note"),
            show="headings", selectmode="browse", style="Ledger.Treeview", height=5)
        font = self.table_font
        for name, title, sample in (("day", "日期", "2026-10-10"), ("category", "分类", "未分类"),
            ("payment", "支付方式", "支付宝"), ("amount_units", "金额（元）", "10,000.00"), ("note", "备注", "一笔日常消费")):
            self.tree.heading(name, text=title, anchor="w", command=lambda key=name: self.sort_table(key))
            width = font.measure(sample) + 25
            self.tree.column(name, width=width, minwidth=width, stretch=name == "note",
                anchor="e" if name == "amount_units" else "w")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.tag_configure("alternate", background="#FAFBFD")
        self.tree.bind("<Double-1>", self._double_click)
        scrollbar = ctk.CTkScrollbar(table, command=self.tree.yview, width=12,
            button_color="#CBD1DF", button_hover_color="#B2BACC")
        scrollbar.grid(row=0, column=1, sticky="ns", padx=(3, 0))
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.empty_label = label(table, "还没有符合条件的记录\n\n在右侧记一笔，或调整筛选条件。", 13, MUTED, justify="center")
        label(records, "搜索支持备注、分类及支付方式 · 点击表头排序，双击修改", 10, MUTED,
            anchor="w").grid(row=5, column=0, sticky="w", padx=16, pady=12)
        self._build_form(page)

    def _build_form(self, page):
        form = ctk.CTkFrame(page, width=278, fg_color="white", corner_radius=12, border_width=1, border_color=LINE)
        form.grid(row=0, column=1, sticky="nsew")
        form.grid_propagate(False)
        form.grid_columnconfigure(0, weight=1)
        label(form, variable=self.form_title_var, size=17, bold=True).grid(row=0, column=0, sticky="w", padx=20, pady=(18, 0))
        label(form, "给这笔消费留个记录", 11, MUTED).grid(row=1, column=0, sticky="w", padx=20, pady=(1, 12))
        amount_header = ctk.CTkFrame(form, fg_color="transparent")
        amount_header.grid(row=2, column=0, sticky="ew", padx=20)
        label(amount_header, "支出金额（元）", 12, MUTED).pack(side="left")
        self.select_product_button = button(amount_header, "选择商品", self.open_product_picker, 82)
        self.select_product_button.configure(height=26, font=(FONT, 11), text_color=ACCENT)
        self.select_product_button.pack(side="right")
        self.amount_entry = entry(form, self.amount_var, 230, 44, 24)
        self.amount_entry.grid(row=3, column=0, sticky="ew", padx=20, pady=(4, 3))
        label(form, "允许记录 0，最多六位小数", 10, MUTED).grid(row=4, column=0, sticky="w", padx=20, pady=(0, 10))
        label(form, "消费日期", 12, MUTED).grid(row=5, column=0, sticky="w", padx=20)
        self.day_entry = CalendarDateEntry(form, self.entry_day_var, width=230)
        self.day_entry.grid(row=6, column=0, sticky="ew", padx=20, pady=(4, 12))
        details = ctk.CTkFrame(form, fg_color="transparent")
        details.grid(row=7, column=0, sticky="ew", padx=20, pady=(0, 12))
        details.grid_columnconfigure((0, 1), weight=1)
        label(details, "消费分类", 12, MUTED).grid(row=0, column=0, sticky="w")
        label(details, "支付方式", 12, MUTED).grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.category_entry = combo(details, self.category_var, self.ledger.categories(), 113, editable=True)
        self.category_entry.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        self.payment_entry = combo(details, self.payment_var, self.ledger.payments(), 113, editable=True)
        self.payment_entry.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(4, 0))
        label(form, "备注（可选）", 12, MUTED).grid(row=8, column=0, sticky="w", padx=20)
        self.note_entry = entry(form, self.note_var, 230, 36)
        self.note_entry.grid(row=9, column=0, sticky="ew", padx=20, pady=(4, 16))
        self.save_button = button(form, "保存支出", self.save, 230, True)
        self.save_button.grid(row=10, column=0, sticky="ew", padx=20)
        self.cancel_button = button(form, "取消修改", self.cancel_edit, 230)
        self.cancel_button.grid(row=11, column=0, sticky="ew", padx=20, pady=(8, 0))
        self.cancel_button.grid_remove()
        self.note_entry.bind("<Return>", lambda event: self.save())
        self.amount_entry.bind("<Return>", lambda event: self.save())

    def _build_products_page(self, page):
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(1, weight=1)
        label(page, "保存常用商品，记账时选择商品即可计算金额。", 12, MUTED).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 14))
        catalog = ctk.CTkFrame(page, fg_color="white", corner_radius=12,
            border_width=1, border_color=LINE)
        catalog.grid(row=1, column=0, sticky="nsew", padx=(0, 16))
        catalog.grid_columnconfigure(0, weight=1)
        catalog.grid_rowconfigure(1, weight=1)
        toolbar = ctk.CTkFrame(catalog, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=18, pady=16)
        label(toolbar, "我的商品", 15, INK, True).pack(side="left")
        label(toolbar, variable=self.product_count_var, size=11, color=MUTED).pack(side="left", padx=12)
        remove = button(toolbar, "删除", self.delete_product, 56)
        remove.configure(text_color=RED)
        remove.pack(side="right")
        button(toolbar, "修改", self.edit_product, 56).pack(side="right", padx=(0, 8))
        table = ctk.CTkFrame(catalog, fg_color="white", corner_radius=0)
        table.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 16))
        table.grid_columnconfigure(0, weight=1)
        table.grid_rowconfigure(0, weight=1)
        self.product_tree = ttk.Treeview(table, columns=("name", "price"), show="headings",
            selectmode="browse", style="Ledger.Treeview")
        self.product_tree.heading("name", text="商品名称", anchor="w")
        self.product_tree.heading("price", text="单价（元）", anchor="e")
        self.product_tree.column("name", width=220, minwidth=120)
        self.product_tree.column("price", width=180, minwidth=180, stretch=False, anchor="e")
        self.product_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ctk.CTkScrollbar(table, command=self.product_tree.yview, width=12)
        scrollbar.grid(row=0, column=1, sticky="ns", padx=(3, 0))
        horizontal = ctk.CTkScrollbar(table, orientation="horizontal", command=self.product_tree.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        self.product_tree.configure(yscrollcommand=scrollbar.set, xscrollcommand=horizontal.set)
        self.product_empty_label = label(table, "还没有商品\n\n在右侧添加名称和价格，之后就能快速记账。", 13, MUTED)
        self.product_tree.bind("<Double-1>", self._double_click_product)
        form = ctk.CTkFrame(page, width=278, fg_color="white", corner_radius=12,
            border_width=1, border_color=LINE)
        form.grid(row=1, column=1, sticky="nsew")
        form.grid_propagate(False)
        form.grid_columnconfigure(0, weight=1)
        label(form, variable=self.product_form_title_var, size=17, bold=True).grid(
            row=0, column=0, sticky="w", padx=20, pady=(20, 18))
        label(form, "商品名称", 12, MUTED).grid(row=1, column=0, sticky="w", padx=20)
        self.product_name_entry = entry(form, self.product_name_var, 230)
        self.product_name_entry.grid(row=2, column=0, sticky="ew", padx=20, pady=(5, 16))
        label(form, "单价（元）", 12, MUTED).grid(row=3, column=0, sticky="w", padx=20)
        self.product_price_entry = entry(form, self.product_price_var, 230, 44, 23)
        self.product_price_entry.grid(row=4, column=0, sticky="ew", padx=20, pady=(5, 5))
        label(form, "允许 0，最多六位小数", 10, MUTED).grid(row=5, column=0, sticky="w", padx=20)
        self.save_product_button = button(form, "保存商品", self.save_product, 230, True)
        self.save_product_button.grid(row=6, column=0, sticky="ew", padx=20, pady=(22, 0))
        self.cancel_product_button = button(form, "取消修改", self.cancel_product_edit, 230)
        self.cancel_product_button.grid(row=7, column=0, sticky="ew", padx=20, pady=(8, 0))
        self.cancel_product_button.grid_remove()
        label(form, "改价或删除商品，已保存的支出金额保持原值。", 11, MUTED,
            wraplength=225, justify="left").grid(row=8, column=0, sticky="w", padx=20, pady=20)
        self.product_price_entry.bind("<Return>", lambda event: self.save_product())

    def refresh_products(self):
        rows = self.ledger.list_products()
        self.product_tree.delete(*self.product_tree.get_children())
        for index, row in enumerate(rows):
            self.product_tree.insert("", "end", iid=str(row["id"]),
                values=(row["name"], format_amount(row["price_units"])),
                tags=("alternate",) if index % 2 else ())
        self.product_tree.tag_configure("alternate", background="#FAFBFD")
        self.product_count_var.set(f"{len(rows)} 个商品")
        if rows:
            self.product_empty_label.place_forget()
        else:
            self.product_empty_label.place(relx=.5, rely=.5, anchor="center")

    def save_product(self):
        try:
            units = parse_amount(self.product_price_var.get())
            name = self.product_name_var.get()
            if self.product_editing_id is None:
                self.ledger.add_product(name, units)
            else:
                self.ledger.update_product(self.product_editing_id, name, units)
        except ValueError as error:
            self._input_error(error)
            return
        self.cancel_product_edit()
        self.status_var.set(f"商品已保存：{name.strip()} · ¥ {format_amount(units)}")
        self.product_tree.delete(*self.product_tree.get_children())
        try:
            self.refresh_products()
        except Exception as error:
            raise RuntimeError(f"商品已保存，但列表刷新失败：{error}。请重新打开商品管理。") from error

    def _selected_product(self):
        selected = self.product_tree.selection()
        if not selected:
            messagebox.showinfo("选择商品", "请先点击要操作的商品。", parent=self)
            return None
        return self.ledger.get_product(int(selected[0]))

    def edit_product(self):
        row = self._selected_product()
        if row is None:
            return
        self.product_editing_id = row["id"]
        self.product_name_var.set(row["name"])
        self.product_price_var.set(format_amount(row["price_units"]).replace(",", ""))
        self.product_form_title_var.set("修改商品")
        self.save_product_button.configure(text="保存修改")
        self.cancel_product_button.grid()
        self.product_name_entry.focus_set()

    def _double_click_product(self, event):
        item = self.product_tree.identify_row(event.y)
        if item:
            self.product_tree.selection_set(item)
            self.edit_product()

    def cancel_product_edit(self):
        self.product_editing_id = None
        self.product_name_var.set("")
        self.product_price_var.set("")
        self.product_form_title_var.set("添加商品")
        self.save_product_button.configure(text="保存商品")
        self.cancel_product_button.grid_remove()

    def delete_product(self):
        row = self._selected_product()
        if row is None:
            return
        if not messagebox.askyesno("删除商品", f"确定删除商品“{row['name']}”？\n已保存的支出金额保持原值。", parent=self):
            return
        self.ledger.delete_product(row["id"])
        if self.product_editing_id == row["id"]:
            self.cancel_product_edit()
        self.status_var.set(f"商品已删除：{row['name']}")
        self.product_tree.delete(*self.product_tree.get_children())
        try:
            self.refresh_products()
        except Exception as error:
            raise RuntimeError(f"商品已删除，但列表刷新失败：{error}。请重新打开商品管理。") from error

    def open_product_picker(self):
        if self.product_picker is not None and self.product_picker.winfo_exists():
            self.product_picker.lift()
            self.product_picker.focus_force()
            return self.product_picker
        rows = self.ledger.list_products()
        if not rows:
            self.show_page("商品管理")
            self.status_var.set("请先添加商品名称和价格，再回到账本选择商品。")
            self.product_name_entry.focus_set()
            return None
        self.product_picker = ProductPicker(self, rows, self.apply_product)
        return self.product_picker

    def apply_product(self, product, quantity, add):
        quantity, units = product_subtotal(product, str(quantity))
        if add and self.amount_var.get().strip():
            units += parse_amount(self.amount_var.get())
        amount = format_amount(units).replace(",", "")
        parse_amount(amount)
        description = f"{product['name']} × {quantity}"
        note = self.note_var.get()
        automatic_note = not note.strip() or note == self.product_note_draft
        if add and note.strip():
            note += f"；{description}"
        elif automatic_note:
            note = description
        self.amount_var.set(amount)
        self.note_var.set(note)
        self.product_note_draft = note if automatic_note else None
        self.status_var.set("商品金额已填入，可手动调整；点击保存支出入账。")

    def _build_calendar_page(self, page):
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(2, weight=1)
        bar = ctk.CTkFrame(page, fg_color="white", corner_radius=12)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        bar.grid_columnconfigure(6, weight=1)
        label(bar, "年度支出", 16, INK, True).grid(row=0, column=0, padx=(16, 12), pady=14)
        self.calendar_previous_button = button(bar, "‹", lambda: self.navigate_calendar(-1), 32)
        self.calendar_previous_button.grid(row=0, column=1, padx=(0, 6))
        self.calendar_year_entry = entry(bar, self.calendar_year_var, 70)
        self.calendar_year_entry.grid(row=0, column=2)
        self.calendar_year_entry.bind("<Return>", lambda event: self.refresh_calendar())
        label(bar, "年", 12, MUTED).grid(row=0, column=3, padx=5)
        self.calendar_next_button = button(bar, "›", lambda: self.navigate_calendar(1), 32)
        self.calendar_next_button.grid(row=0, column=4, padx=(0, 8))
        self.calendar_query_button = button(bar, "查看", self.refresh_calendar, 56)
        self.calendar_query_button.grid(row=0, column=5)
        button(bar, "今年", lambda: self.refresh_calendar(date.today().year), 56).grid(
            row=0, column=6, sticky="w", padx=8)
        label(bar, variable=self.calendar_total_var, size=21, color=ACCENT, bold=True).grid(
            row=0, column=7, padx=(12, 16))
        detail = ctk.CTkFrame(page, fg_color="transparent")
        detail.grid(row=1, column=0, sticky="ew", padx=4, pady=(0, 8))
        label(detail, variable=self.calendar_count_var, size=11, color=MUTED).pack(side="left")
        label(detail, "每日金额（元） · — 未记账 · 0.00 零支出 · 点击日期查看明细",
            11, MUTED).pack(side="right")
        self.year_calendar = YearExpenseCalendar(page, self.open_calendar_day)
        self.year_calendar.grid(row=2, column=0, sticky="nsew")

    def refresh_calendar(self, year=None):
        if year is None:
            text = self.calendar_year_var.get().strip()
            try:
                if not text.isascii() or not text.isdecimal() or len(text) > 4:
                    raise ValueError("年份请填写 1～9999 之间的整数。")
                year = int(text)
                if not 1 <= year <= 9999:
                    raise ValueError("年份请填写 1～9999 之间的整数。")
            except ValueError as error:
                self._input_error(error)
                return
        summary = self.ledger.year_summary(year)
        self.year_calendar.set_year(year, summary["by_day"], self.calendar_selected_day)
        self.calendar_year = year
        self.calendar_year_var.set(str(year))
        self.calendar_total_var.set(f"¥ {format_amount(summary['total_units'])}")
        self.calendar_count_var.set(f"{summary['count']} 笔 · {len(summary['by_day'])} 个记账日")
        self.calendar_previous_button.configure(state="disabled" if year == 1 else "normal")
        self.calendar_next_button.configure(state="disabled" if year == 9999 else "normal")
        self.status_var.set(f"{year} 年支出日历已更新，点击日期查看当天明细。")

    def navigate_calendar(self, offset):
        self.refresh_calendar(self.calendar_year + offset)

    def open_calendar_day(self, day):
        self.calendar_selected_day = day
        self.view_day_var.set(day)
        self.filter_category_var.set("全部分类")
        self.filter_payment_var.set("全部方式")
        self.keyword_var.set("")
        self.load_day()
        self.show_page("账本明细", refresh=False)
        self.status_var.set(f"正在查看 {day} 的全部支出。")

    def _build_reports_page(self, page):
        page.grid_columnconfigure(0, weight=3)
        page.grid_columnconfigure(1, weight=2)
        page.grid_rowconfigure(2, weight=1)
        bar = ctk.CTkFrame(page, fg_color="transparent")
        bar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        label(bar, "月度统计", 16, INK, True).pack(side="left")
        label(bar, "选择任意日期查看所在月份", 11, MUTED).pack(side="left", padx=12)
        CalendarDateEntry(bar, self.report_day_var, command=self.refresh_reports, width=166).pack(side="right")
        metrics = ctk.CTkFrame(page, fg_color="white", corner_radius=12)
        metrics.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        metrics.grid_columnconfigure((0, 1, 2), weight=1)
        for index, (title, variable) in enumerate((("当月总支出", self.report_total_var),
            ("当月记账笔数", self.report_count_var), ("日均支出 · 按当月天数", self.report_average_var))):
            item = ctk.CTkFrame(metrics, fg_color="transparent")
            item.grid(row=0, column=index, sticky="ew", padx=20, pady=14)
            label(item, title, 11, MUTED).pack(anchor="w")
            label(item, variable=variable, size=24, bold=True).pack(anchor="w")
        trend = ctk.CTkFrame(page, fg_color="white", corner_radius=12)
        trend.grid(row=2, column=0, sticky="nsew", padx=(0, 14))
        trend.grid_columnconfigure(0, weight=1)
        trend.grid_rowconfigure(1, weight=1)
        label(trend, "每日支出趋势", 14, INK, True).grid(row=0, column=0, sticky="w", padx=20, pady=(18, 0))
        self.trend_canvas = tk.Canvas(trend, bg="white", highlightthickness=0)
        self.trend_canvas.grid(row=1, column=0, sticky="nsew", padx=12, pady=12)
        self.trend_canvas.bind("<Configure>", lambda event: self.draw_trend())
        category = ctk.CTkFrame(page, fg_color="white", corner_radius=12)
        category.grid(row=2, column=1, sticky="nsew")
        category.grid_columnconfigure(0, weight=1)
        category.grid_rowconfigure(1, weight=1)
        label(category, "分类支出排行", 14, INK, True).grid(row=0, column=0, sticky="w", padx=20, pady=(18, 6))
        self.category_chart = ctk.CTkScrollableFrame(category, fg_color="white", corner_radius=0)
        self.category_chart.grid(row=1, column=0, sticky="nsew", padx=12, pady=8)

    def _build_budget_page(self, page):
        page.grid_columnconfigure((0, 1), weight=1)
        page.grid_rowconfigure(0, weight=1)
        form = ctk.CTkFrame(page, fg_color="white", corner_radius=12)
        form.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        label(form, "设置月预算", 18, INK, True).pack(anchor="w", padx=26, pady=(25, 6))
        label(form, "按实际支出，看看这个月还剩多少空间。", 12, MUTED).pack(anchor="w", padx=26, pady=(0, 24))
        label(form, "预算月份 · 选择该月任意日期", 12, MUTED).pack(anchor="w", padx=26)
        CalendarDateEntry(form, self.budget_day_var, command=self.refresh_budget, width=260).pack(anchor="w", padx=26, pady=(7, 22))
        label(form, "每月预算金额（元）", 12, MUTED).pack(anchor="w", padx=26)
        entry(form, self.budget_amount_var, 260, 48, 23).pack(anchor="w", padx=26, pady=(7, 20))
        self.budget_save_button = button(form, "保存本月预算", self.save_budget, 260, True)
        self.budget_save_button.pack(anchor="w", padx=26)
        button(form, "移除本月预算", self.clear_budget, 260).pack(anchor="w", padx=26, pady=(10, 0))
        label(form, "预算需要你设置，未设置的月份不会推测预算。", 11, MUTED,
            wraplength=310, justify="left").pack(anchor="w", padx=26, pady=26)
        progress = ctk.CTkFrame(page, fg_color="white", corner_radius=12)
        progress.grid(row=0, column=1, sticky="nsew")
        label(progress, "本月预算进度", 18, INK, True).pack(anchor="w", padx=26, pady=(25, 20))
        label(progress, "计划预算", 12, MUTED).pack(anchor="w", padx=26)
        label(progress, variable=self.budget_total_var, size=30, bold=True).pack(anchor="w", padx=26, pady=(4, 24))
        label(progress, "当月已支出", 12, MUTED).pack(anchor="w", padx=26)
        label(progress, variable=self.budget_spent_var, size=23, bold=True).pack(anchor="w", padx=26, pady=(4, 20))
        self.budget_progress = ctk.CTkProgressBar(progress, height=9, progress_color=ACCENT, fg_color=PALE)
        self.budget_progress.pack(fill="x", padx=26, pady=(0, 18))
        self.budget_progress.set(0)
        label(progress, variable=self.budget_remaining_var, size=16, color=ACCENT, bold=True,
            wraplength=310, justify="left").pack(anchor="w", padx=26)
        label(progress, "预算按整月支出计算，不受明细筛选影响。", 11, MUTED,
            wraplength=310, justify="left").pack(anchor="w", padx=26, pady=25)

    def _build_backup_page(self, page):
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(2, weight=1)
        for row, title, description, controls in (
            (0, "导出消费明细", "将当前明细列表导出为 CSV，可用 Excel 打开。", [("导出 CSV", self.export_current)]),
            (1, "账本备份与恢复", "备份包含全部记录、月预算和商品。恢复前会另存当前账本。",
             [("保存备份", self.backup_ledger), ("从备份恢复", self.restore_ledger)])):
            card = ctk.CTkFrame(page, fg_color="white", corner_radius=12)
            card.grid(row=row, column=0, sticky="ew", pady=(0, 16))
            card.grid_columnconfigure(0, weight=1)
            label(card, title, 17, INK, True).grid(row=0, column=0, sticky="w", padx=24, pady=(20, 5))
            label(card, description, 12, MUTED).grid(row=1, column=0, sticky="w", padx=24, pady=(0, 20))
            actions = ctk.CTkFrame(card, fg_color="transparent")
            actions.grid(row=0, column=1, rowspan=2, padx=24)
            for index, (text, command) in enumerate(controls):
                button(actions, text, command, 110, primary=index == 0).pack(side="left", padx=(8, 0))
        info = ctk.CTkFrame(page, fg_color="white", corner_radius=12)
        info.grid(row=2, column=0, sticky="nsew")
        label(info, "本地账本", 17, INK, True).pack(anchor="w", padx=24, pady=(20, 8))
        label(info, "账本文件", 12, MUTED).pack(anchor="w", padx=24)
        label(info, str(self.ledger.path), 12, INK, wraplength=700, justify="left").pack(anchor="w", padx=24, pady=(4, 15))
        label(info, variable=self.storage_var, size=12, color=MUTED).pack(anchor="w", padx=24)
        label(info, "移动软件时，请将整个软件文件夹和 data 文件夹一起保留。", 12, MUTED).pack(anchor="w", padx=24, pady=18)

    def show_page(self, name, refresh=True):
        if refresh:
            if name == "支出日历":
                self.refresh_calendar(self.calendar_year)
            elif name == "商品管理":
                self.refresh_products()
            elif name == "统计分析":
                self.refresh_reports()
            elif name == "预算管理":
                self.refresh_budget()
            elif name == "数据备份":
                self.storage_var.set(f"已保存 {len(self.ledger.list_entries())} 笔消费记录 · 账本大小 {self.ledger.path.stat().st_size / 1024:.1f} KB")
        self.overview.grid() if name == "账本明细" else self.overview.grid_remove()
        for title, page in self.pages.items():
            page.grid() if title == name else page.grid_remove()
            self.nav_buttons[title].configure(fg_color=PALE if title == name else "white",
                text_color=ACCENT if title == name else MUTED)
        self.page_title_var.set(name)

    def focus_form(self):
        self._reset_form()
        self.entry_day_var.set(date.today().isoformat())
        self.show_page("账本明细")
        self.status_var.set("记一笔新的支出。")
        self.amount_entry.focus_set()

    def _input_error(self, error):
        self.status_var.set(f"输入有误：{error}")
        messagebox.showwarning("请检查输入", str(error), parent=self)

    def apply_filters(self):
        mode = self.period_var.get()
        self.range_frame.grid() if mode == "自定义" else self.range_frame.grid_remove()
        try:
            if mode == "全部":
                start = end = None
            elif mode == "自定义":
                start, end = parse_day(self.range_start_var.get()), parse_day(self.range_end_var.get())
                if start > end:
                    raise ValueError("开始日期不能晚于结束日期。")
            else:
                day = parse_day(self.view_day_var.get())
                if mode == "当天":
                    start = end = day
                elif mode == "本月":
                    first = date.fromisoformat(day).replace(day=1)
                    start = first.isoformat()
                    end = first.replace(day=calendar.monthrange(first.year, first.month)[1]).isoformat()
                else:
                    raise ValueError(f"不支持的日期范围：{mode}")
        except ValueError as error:
            self._input_error(error)
            return
        category, payment = self.filter_category_var.get(), self.filter_payment_var.get()
        rows = self.ledger.list_entries(start, end, None if category == "全部分类" else category,
            None if payment == "全部方式" else payment, self.keyword_var.get().strip())
        today = date.today().isoformat()
        today_total = sum(row["amount_units"] for row in self.ledger.list_day(today))
        month_total = self.ledger.month_summary(today[:7])["total_units"]
        self.entries = {str(row["id"]): row for row in rows}
        if mode == "当天":
            self.displayed_day = start
        self.total_var.set(f"¥ {format_amount(sum(row['amount_units'] for row in rows))}")
        self.count_var.set(str(len(rows)))
        self.today_total_var.set(f"¥ {format_amount(today_total)}")
        self.month_total_var.set(f"¥ {format_amount(month_total)}")
        self.day_label_var.set(f"{start} 支出" if mode == "当天" else "筛选支出")
        self._render_rows()

    def _render_rows(self):
        self.tree.delete(*self.tree.get_children())
        rows = sorted(self.entries.values(), key=lambda row: (row[self.sort_key], row["id"]), reverse=self.sort_reverse)
        for index, row in enumerate(rows):
            self.tree.insert("", "end", iid=str(row["id"]), values=(row["day"], row["category"], row["payment"],
                format_amount(row["amount_units"]), row["note"]), tags=("alternate",) if index % 2 else ())
        if rows:
            self.empty_label.place_forget()
        else:
            self.empty_label.configure(text="还没有符合条件的记录\n\n在右侧记一笔，或调整筛选条件。")
            self.empty_label.place(relx=.5, rely=.55, anchor="center")

    def sort_table(self, key):
        self.sort_reverse = not self.sort_reverse if self.sort_key == key else False
        self.sort_key = key
        self._render_rows()

    def load_day(self):
        self.period_var.set("当天")
        self.apply_filters()

    def save(self):
        try:
            day, units = parse_day(self.entry_day_var.get()), parse_amount(self.amount_var.get())
            category, payment = self.category_var.get().strip(), self.payment_var.get().strip()
            if not category or not payment:
                raise ValueError("分类与支付方式不能为空，未确定时请选择“未分类”“未指定”。")
        except ValueError as error:
            self._input_error(error)
            return
        note = self.note_var.get().strip()
        editing = self.editing_id is not None
        if editing:
            self.ledger.update(self.editing_id, day, units, note, category, payment)
        else:
            self.ledger.add(day, units, note, category, payment)
        self._reset_form()
        self.entry_day_var.set(day)
        self._refresh_after_write(day, f"已{'修改' if editing else '保存'}：{day} · ¥ {format_amount(units)}")

    def _refresh_after_write(self, day, confirmation):
        self.view_day_var.set(day)
        self.filter_category_var.set("全部分类")
        self.filter_payment_var.set("全部方式")
        self.keyword_var.set("")
        self.status_var.set(confirmation)
        self._clear_records()
        try:
            self.load_day()
            self._refresh_options()
        except Exception as error:
            raise RuntimeError(f"{confirmation}。账本已提交，但明细刷新失败：{error}。请重新查询明细。") from error

    def _clear_records(self):
        self.entries = {}
        self.tree.delete(*self.tree.get_children())
        self.total_var.set("待刷新")
        self.count_var.set("待刷新")
        self.empty_label.configure(text="明细待刷新，请重新查询。")
        self.empty_label.place(relx=.5, rely=.55, anchor="center")

    def _refresh_options(self):
        categories, payments = self.ledger.categories(), self.ledger.payments()
        self.category_entry.configure(values=categories)
        self.payment_entry.configure(values=payments)
        self.filter_category.configure(values=["全部分类", *categories])
        self.filter_payment.configure(values=["全部方式", *payments])

    def _selected_record(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("选择一条记录", "请先点击要操作的支出记录。", parent=self)
            return None
        return self.entries[selected[0]]

    def edit_selected(self):
        row = self._selected_record()
        if row is None:
            return
        self.editing_id = row["id"]
        self.product_note_draft = None
        self.entry_day_var.set(row["day"])
        self.amount_var.set(format_amount(row["amount_units"]).replace(",", ""))
        self.note_var.set(row["note"])
        self.category_var.set(row["category"])
        self.payment_var.set(row["payment"])
        self.form_title_var.set("修改记录")
        self.save_button.configure(text="保存修改")
        self.cancel_button.grid()
        self.status_var.set("正在修改记录，保存后生效。")
        self.amount_entry.focus_set()
        self.amount_entry.select_range(0, tk.END)

    def _double_click(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.edit_selected()

    def delete_selected(self):
        row = self._selected_record()
        if row is None:
            return
        if not messagebox.askyesno("删除支出", f"确定删除这笔支出？\n\n日期：{row['day']}\n"
            f"金额：¥ {format_amount(row['amount_units'])}\n分类：{row['category']}\n备注：{row['note']}\n\n删除后无法撤销。", parent=self):
            return
        self.ledger.delete(row["id"])
        if self.editing_id == row["id"]:
            self._reset_form()
        self._refresh_after_write(row["day"], f"已删除：¥ {format_amount(row['amount_units'])}")

    def _reset_form(self):
        self.editing_id = None
        self.product_note_draft = None
        self.amount_var.set("")
        self.note_var.set("")
        self.form_title_var.set("记一笔")
        self.save_button.configure(text="保存支出")
        self.cancel_button.grid_remove()

    def cancel_edit(self):
        self._reset_form()
        self.entry_day_var.set(date.today().isoformat())
        self.category_var.set("未分类")
        self.payment_var.set("未指定")
        self.status_var.set("已取消修改，原记录未改变。")

    def navigate(self, offset):
        try:
            day = date.fromisoformat(parse_day(self.view_day_var.get()))
        except ValueError as error:
            self._input_error(error)
            return
        self.view_day_var.set((day + timedelta(days=offset)).isoformat())
        self.load_day()

    def show_today(self):
        self.view_day_var.set(date.today().isoformat())
        self.load_day()

    def refresh_reports(self):
        try:
            day = parse_day(self.report_day_var.get())
        except ValueError as error:
            self._input_error(error)
            return
        summary = self.ledger.month_summary(day[:7])
        self.chart_data = summary
        self.chart_month = date.fromisoformat(day).replace(day=1)
        self.report_total_var.set(f"¥ {format_amount(summary['total_units'])}")
        self.report_count_var.set(f"{summary['count']} 笔")
        days = calendar.monthrange(int(day[:4]), int(day[5:7]))[1]
        self.report_average_var.set(f"¥ {format_amount((summary['total_units'] + days // 2) // days)}")
        for child in self.category_chart.winfo_children():
            child.destroy()
        total = summary["total_units"]
        if not summary["by_category"]:
            label(self.category_chart, "这个月还没有支出记录", 13, MUTED).pack(pady=45)
        for index, (name, amount) in enumerate(summary["by_category"]):
            row = ctk.CTkFrame(self.category_chart, fg_color="transparent")
            row.pack(fill="x", padx=6, pady=(8, 12))
            label(row, name, 13, INK, True).pack(side="left")
            label(row, f"¥ {format_amount(amount)}", 12, INK).pack(side="right")
            bar = ctk.CTkProgressBar(self.category_chart, height=7, fg_color="#F1F2F6",
                progress_color=(ACCENT, GREEN, "#E9AA56", "#D884AC")[index % 4])
            bar.pack(fill="x", padx=6)
            bar.set(amount / total)
            label(self.category_chart, f"占当月支出 {amount / total:.1%}", 10, MUTED).pack(anchor="w", padx=6, pady=(3, 8))
        self.draw_trend()

    def draw_trend(self):
        canvas = self.trend_canvas
        canvas.delete("all")
        width, height = canvas.winfo_width(), canvas.winfo_height()
        if width < 150 or height < 100:
            return
        if not self.chart_data["by_day"]:
            canvas.create_text(width / 2, height / 2, text="这个月还没有支出记录", fill=MUTED, font=(FONT, 10))
            return
        if self.chart_data["total_units"] == 0:
            canvas.create_text(width / 2, height / 2, text="这个月已记账，支出合计为 ¥ 0.00", fill=MUTED, font=(FONT, 10))
            return
        day = self.chart_month
        count = calendar.monthrange(day.year, day.month)[1]
        values = [self.chart_data["by_day"].get(f"{day.year:04d}-{day.month:02d}-{number:02d}", 0)
            for number in range(1, count + 1)]
        peak = max(values)
        scale = self._get_window_scaling()
        font = (FONT, -round(11 * scale))
        left, right, top, bottom = round(70 * scale), width - round(22 * scale), round(30 * scale), height - round(38 * scale)
        for step in range(5):
            y = bottom - (bottom - top) * step / 4
            canvas.create_line(left, y, right, y, fill=LINE)
            canvas.create_text(left - round(9 * scale), y, text=format_amount(peak * step // 4), anchor="e", fill=MUTED, font=font)
        points = []
        for index, value in enumerate(values):
            x = left + (right - left) * index / (count - 1)
            y = bottom - (bottom - top) * value / peak
            points.extend((x, y))
            if index in (0, 7, 14, 21, count - 1):
                canvas.create_text(x, bottom + round(19 * scale), text=f"{index + 1}日", fill=MUTED, font=font)
        canvas.create_polygon(left, bottom, *points, right, bottom, fill="#F2EEFF", outline="")
        canvas.create_line(*points, fill=ACCENT, width=3, joinstyle="round")
        for index, value in enumerate(values):
            if value:
                x, y = points[index * 2:index * 2 + 2]
                canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill=ACCENT, outline="white")

    def refresh_budget(self):
        try:
            month = parse_day(self.budget_day_var.get())[:7]
        except ValueError as error:
            self._input_error(error)
            return
        amount = self.ledger.get_budget(month)
        spent = self.ledger.month_summary(month)["total_units"]
        self.budget_spent_var.set(f"¥ {format_amount(spent)}")
        if amount is None:
            self.budget_amount_var.set("")
            self.budget_total_var.set("未设置")
            self.budget_remaining_var.set("这个月还没有设置预算")
            self.budget_progress.set(0)
        else:
            self.budget_amount_var.set(format_amount(amount).replace(",", ""))
            self.budget_total_var.set(f"¥ {format_amount(amount)}")
            remaining = amount - spent
            self.budget_remaining_var.set(f"{'剩余预算' if remaining >= 0 else '已超出预算'}  ¥ {format_amount(abs(remaining))}")
            self.budget_progress.configure(progress_color=ACCENT if remaining >= 0 else RED)
            self.budget_progress.set(min(spent / amount, 1))

    def save_budget(self):
        try:
            month = parse_day(self.budget_day_var.get())[:7]
            amount = parse_amount(self.budget_amount_var.get())
            if amount == 0:
                raise ValueError("月预算必须大于 0。")
        except ValueError as error:
            self._input_error(error)
            return
        self.ledger.set_budget(month, amount)
        self.status_var.set(f"已保存 {month} 的月预算")
        try:
            self.refresh_budget()
        except Exception as error:
            raise RuntimeError(f"已保存 {month} 的月预算，但预算显示刷新失败：{error}。请重新选择预算月份。") from error

    def clear_budget(self):
        try:
            month = parse_day(self.budget_day_var.get())[:7]
        except ValueError as error:
            self._input_error(error)
            return
        if messagebox.askyesno("移除月预算", f"移除 {month} 的预算？消费记录会保留。", parent=self):
            self.ledger.clear_budget(month)
            self.status_var.set(f"已移除 {month} 的月预算")
            try:
                self.refresh_budget()
            except Exception as error:
                raise RuntimeError(f"已移除 {month} 的月预算，但预算显示刷新失败：{error}。请重新选择预算月份。") from error

    def export_current(self):
        destination = filedialog.asksaveasfilename(parent=self, title="导出当前消费明细",
            defaultextension=".csv", initialfile=f"消费明细-{date.today().isoformat()}.csv", filetypes=[("CSV 文件", "*.csv")])
        if not destination:
            return
        rows = [self.entries[item] for item in self.tree.get_children()]
        self.ledger.export_csv(Path(destination), rows)
        self.status_var.set(f"已导出 {len(rows)} 条明细：{destination}")

    def backup_ledger(self):
        destination = filedialog.asksaveasfilename(parent=self, title="保存账本备份",
            defaultextension=".sqlite3", initialfile=f"账本备份-{datetime.now():%Y%m%d-%H%M%S}.sqlite3",
            filetypes=[("SQLite 账本", "*.sqlite3")])
        if not destination:
            return
        self.ledger.backup(Path(destination))
        self.status_var.set(f"账本已备份：{destination}")

    def restore_ledger(self):
        source = filedialog.askopenfilename(parent=self, title="选择账本备份", filetypes=[("SQLite 账本", "*.sqlite3")])
        if not source:
            return
        if not messagebox.askyesno("恢复账本", "恢复会用备份替换当前记录、预算和商品。\n"
            "当前账本会先自动保存到 backups 文件夹。\n\n确定继续？", parent=self):
            return
        backups = self.ledger.path.parent / "backups"
        backups.mkdir(exist_ok=True)
        self.ledger.backup(backups / f"before-restore-{datetime.now():%Y%m%d-%H%M%S-%f}.sqlite3")
        self.ledger.restore(Path(source))
        if self.product_picker is not None and self.product_picker.winfo_exists():
            self.product_picker.destroy()
        self.product_picker = None
        self.cancel_product_edit()
        self.product_tree.delete(*self.product_tree.get_children())
        self.cancel_edit()
        self._clear_records()
        self.view_day_var.set(date.today().isoformat())
        self.period_var.set("本月")
        self.filter_category_var.set("全部分类")
        self.filter_payment_var.set("全部方式")
        self.keyword_var.set("")
        try:
            self._refresh_options()
            self.apply_filters()
        except Exception as error:
            raise RuntimeError(f"账本已恢复，但明细刷新失败：{error}。请重新查询明细。恢复前的账本位于 {backups}。") from error
        self.status_var.set("账本已恢复。恢复前的账本已另存到 backups 文件夹。")
        self.show_page("账本明细")

    def report_callback_exception(self, exc, value, tb):
        LOGGER.error("界面操作失败；账本=%s", self.ledger.path, exc_info=(exc, value, tb))
        self.status_var.set(f"操作失败：{value}")
        messagebox.showerror("操作失败", f"{exc.__name__}：{value}\n\n操作未能完整完成，请检查账本后再操作。\n"
            f"账本：{self.ledger.path}\n详细错误：{DATA_DIR / 'errors.log'}", parent=self)

    def destroy(self):
        # 计时器应由注册它的控件释放，避免 CTk 窗口销毁后留下无效 Tcl command。
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


def main():
    try:
        DATA_DIR.mkdir(exist_ok=True)
        logging.basicConfig(filename=DATA_DIR / "errors.log", encoding="utf-8",
            level=logging.ERROR, format="%(asctime)s %(levelname)s %(message)s")
        ledger = Ledger(DATA_DIR / "ledger.sqlite3")
        try:
            window = LedgerApp(ledger)
            window.mainloop()
        finally:
            ledger.close()
    except Exception:
        details = traceback.format_exc()
        LOGGER.exception("记账软件启动或运行失败")
        ctypes.windll.user32.MessageBoxW(None, f"记账软件未能正常运行。\n\n{details}\n"
            f"账本位置：{DATA_DIR / 'ledger.sqlite3'}", "记账软件运行失败", 0x10)
        raise


if __name__ == "__main__":
    main()
