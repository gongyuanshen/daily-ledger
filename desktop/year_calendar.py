"""用一张画布展示全年支出，日期金额沿用账本的整数微元格式。"""
import calendar
from datetime import date
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

import customtkinter as ctk

from ledger import format_amount


BG, INK, MUTED = "#F5F6FA", "#232B42", "#8A91A4"
ACCENT, LINE, PALE = "#6C5CE7", "#E9ECF3", "#F0EDFF"
FONT = "Microsoft YaHei UI"


class YearExpenseCalendar(ctk.CTkFrame):
    def __init__(self, master, on_day_selected, **kwargs):
        kwargs.setdefault("fg_color", BG)
        kwargs.setdefault("corner_radius", 0)
        super().__init__(master, **kwargs)
        self.on_day_selected = on_day_selected
        self.year = None
        self.selected_day = None
        self.day_items = {}
        self.day_bounds = {}
        self.day_positions = {}
        self.month_items = {}
        self.month_bounds = {}
        self.month_totals = {}
        self._amount_text = {}
        self._recorded_days = set()
        self._item_days = {}
        self._weeks = {}
        self._hover_day = None
        self._layout_after_id = None
        self._layout_width = None
        scale = self._get_widget_scaling()
        self.day_font = tkfont.Font(self, family=FONT, size=-round(10 * scale))
        self.title_font = tkfont.Font(self, family=FONT, size=-round(14 * scale), weight="bold")
        self.total_font = tkfont.Font(self, family=FONT, size=-round(10 * scale))
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(
            self, bg=BG, highlightthickness=0, borderwidth=0,
            xscrollincrement=round(20 * scale), yscrollincrement=round(20 * scale))
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self._scroll_style = ttk.Style(self)
        for orientation in ("Vertical", "Horizontal"):
            name = f"YearExpense.{orientation}.TScrollbar"
            self._scroll_style.layout(name, [
                (f"{orientation}.Scrollbar.trough", {"sticky": "nswe", "children": [
                    (f"{orientation}.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
            self._scroll_style.configure(
                name, background="#CBD1DF", troughcolor=BG, bordercolor=BG,
                lightcolor="#CBD1DF", darkcolor="#CBD1DF", width=round(12 * scale))
            self._scroll_style.map(name, background=[("active", "#B2BACC")])
        self.vertical_scrollbar = ttk.Scrollbar(
            self, orient="vertical", command=self.canvas.yview,
            style="YearExpense.Vertical.TScrollbar", takefocus=False)
        self.vertical_scrollbar.grid(row=0, column=1, sticky="ns")
        self.horizontal_scrollbar = ttk.Scrollbar(
            self, orient="horizontal", command=self.canvas.xview,
            style="YearExpense.Horizontal.TScrollbar", takefocus=False)
        self.horizontal_scrollbar.grid(row=1, column=0, sticky="ew")
        self.canvas.configure(yscrollcommand=self.vertical_scrollbar.set,
                              xscrollcommand=self.horizontal_scrollbar.set)
        self.canvas.bind("<Configure>", self._sync_layout)
        self.canvas.bind("<Motion>", self._mouse_motion)
        self.canvas.bind("<Leave>", self._mouse_leave)
        self.canvas.bind("<ButtonRelease-1>", self._mouse_release)
        self._wheel_owner = self.winfo_toplevel()
        self._wheel_binding = self._wheel_owner.bind("<MouseWheel>", self._mouse_wheel, add="+")

    def set_year(self, year: int, totals: dict[str, int], selected_day: str | None = None):
        date(year, 1, 1)
        month_totals = {month: 0 for month in range(1, 13)}
        for day, amount in totals.items():
            value = date.fromisoformat(day)
            if value.year == year:
                month_totals[value.month] += amount
        self.canvas.delete("all")
        self.year = year
        self.selected_day = selected_day
        self.day_items.clear()
        self.day_bounds.clear()
        self.day_positions.clear()
        self.month_items.clear()
        self.month_bounds.clear()
        self._amount_text.clear()
        self._item_days.clear()
        self._recorded_days = set(totals)
        self.month_totals = month_totals
        self._hover_day = None
        self.canvas.configure(cursor="")
        today = date.today().isoformat()
        month_calendar = calendar.Calendar(firstweekday=0)
        self._weeks = {month: month_calendar.monthdayscalendar(year, month)
                       for month in range(1, 13)}
        for month in range(1, 13):
            self.month_items[month] = {
                "background": self.canvas.create_polygon(
                    0, 0, 0, 0, 0, 0, fill="white", outline=LINE,
                    smooth=True, splinesteps=12, state="hidden", tags=("calendar", "month")),
                "title": self.canvas.create_text(
                    0, 0, text=f"{month}月", font=self.title_font, fill=INK, anchor="w",
                    state="hidden", tags="calendar"),
                "total": self.canvas.create_text(
                    0, 0, text=f"¥ {format_amount(month_totals[month])}",
                    font=self.total_font, fill=MUTED, anchor="e", state="hidden", tags="calendar"),
                "weekday": tuple(self.canvas.create_text(
                    0, 0, text=weekday, font=self.day_font, fill=MUTED,
                    state="hidden", tags="calendar")
                    for weekday in "一二三四五六日")}
            for row, week in enumerate(self._weeks[month]):
                for column, number in enumerate(week):
                    if number == 0:
                        continue
                    day = date(year, month, number).isoformat()
                    amount = format_amount(totals[day]) if day in totals else "—"
                    self._amount_text[day] = amount
                    self.day_positions[day] = month, row, column
                    selected = day == selected_day
                    text_color = "white" if selected else (INK if day in totals else MUTED)
                    tags = ("calendar", "day", f"day:{day}")
                    items = (
                        self.canvas.create_rectangle(
                            0, 0, 0, 0, fill=ACCENT if selected else "white",
                            outline=ACCENT if day == today else "",
                            width=round(self._get_widget_scaling()) if day == today else 0,
                            state="hidden", tags=tags),
                        self.canvas.create_text(
                            0, 0, text=str(number), font=self.day_font, fill=text_color,
                            state="hidden", tags=tags),
                        self.canvas.create_text(
                            0, 0, text=amount, font=self.day_font, fill=text_color,
                            state="hidden", tags=tags))
                    self.day_items[day] = items
                    self._item_days.update((item, day) for item in items)
        self._measure_minimum_width()
        self._layout_width = None
        self._sync_layout()

    def _measure_minimum_width(self):
        scale = self._get_widget_scaling()
        widest_amount = max(self.day_font.measure(text) for text in set(self._amount_text.values()))
        day_width = max(round(30 * scale), widest_amount + round(10 * scale))
        header_width = max(
            self.title_font.measure(f"{month}月")
            + self.total_font.measure(f"¥ {format_amount(self.month_totals[month])}")
            + round(30 * scale) for month in range(1, 13))
        self._minimum_month_width = max(day_width * 7 + round(16 * scale), header_width)

    def _sync_layout(self, event=None):
        # 每轮空闲只布局一次；不逐个创建子窗口，也不嵌套处理 Tk 事件。
        if self._layout_after_id is None:
            self._layout_after_id = self.after_idle(self._layout)

    def _layout(self):
        self._layout_after_id = None
        if self.year is None:
            return
        scale = self._get_widget_scaling()
        outer, gap = round(4 * scale), round(8 * scale)
        width = max(self.canvas.winfo_width(), 3 * self._minimum_month_width + 2 * gap + 2 * outer)
        if width == self._layout_width:
            return
        self._layout_width = width
        card_width = (width - 2 * outer - 2 * gap) / 3
        inner, heading = round(8 * scale), round(39 * scale)
        radius = round(10 * scale)
        weekday_height, cell_height = round(22 * scale), round(44 * scale)
        bottom, row_gap = round(8 * scale), round(10 * scale)
        row_heights = [heading + weekday_height + cell_height * max(
            len(self._weeks[month]) for month in range(row * 3 + 1, row * 3 + 4)) + bottom
            for row in range(4)]
        y = outer
        for row, row_height in enumerate(row_heights):
            for column in range(3):
                month = row * 3 + column + 1
                x = outer + column * (card_width + gap)
                self.month_bounds[month] = (x, y, x + card_width, y + row_height)
                items = self.month_items[month]
                right, lower = x + card_width, y + row_height
                self.canvas.coords(
                    items["background"],
                    x + radius, y, x + radius, y,
                    right - radius, y, right - radius, y,
                    right, y, right, y + radius, right, y + radius,
                    right, lower - radius, right, lower - radius, right, lower,
                    right - radius, lower, right - radius, lower,
                    x + radius, lower, x + radius, lower,
                    x, lower, x, lower - radius, x, lower - radius,
                    x, y + radius, x, y + radius, x, y)
                self.canvas.coords(items["title"], x + round(10 * scale), y + heading / 2)
                self.canvas.coords(items["total"], x + card_width - round(10 * scale), y + heading / 2)
                cell_width = (card_width - 2 * inner) / 7
                for weekday, item in enumerate(items["weekday"]):
                    self.canvas.coords(item, x + inner + (weekday + 0.5) * cell_width,
                                       y + heading + weekday_height / 2)
            y += row_height + row_gap
        for day, (month, row, column) in self.day_positions.items():
            x, y0, x1, _ = self.month_bounds[month]
            cell_width = (x1 - x - 2 * inner) / 7
            left = x + inner + column * cell_width + round(scale)
            top = y0 + heading + weekday_height + row * cell_height + round(scale)
            right = x + inner + (column + 1) * cell_width - round(scale)
            lower = top + cell_height - 2 * round(scale)
            self.day_bounds[day] = (left, top, right, lower)
            background, number, amount = self.day_items[day]
            self.canvas.coords(background, left, top, right, lower)
            self.canvas.coords(number, (left + right) / 2, top + round(12 * scale))
            self.canvas.coords(amount, (left + right) / 2, top + round(29 * scale))
        height = 2 * outer + sum(row_heights) + 3 * row_gap
        self.canvas.configure(scrollregion=(0, 0, width, height))
        # 所有边界和坐标完成后统一显示，未布局图元不参与鼠标命中。
        self.canvas.itemconfigure("calendar", state="normal")

    def _day_at(self, event):
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        for item in reversed(self.canvas.find_overlapping(x, y, x, y)):
            if item in self._item_days:
                day = self._item_days[item]
                x0, y0, x1, y1 = self.day_bounds[day]
                if x0 <= x < x1 and y0 <= y < y1:
                    return day
        return None

    def _paint_day(self, day):
        background, number, amount = self.day_items[day]
        selected = day == self.selected_day
        hovered = day == self._hover_day
        fill = ("#5A49D1" if hovered else ACCENT) if selected else (PALE if hovered else "white")
        text_color = "white" if selected else (INK if day in self._recorded_days else MUTED)
        self.canvas.itemconfigure(background, fill=fill)
        self.canvas.itemconfigure(number, fill=text_color)
        self.canvas.itemconfigure(amount, fill=text_color)

    def _mouse_motion(self, event):
        day = self._day_at(event)
        if day == self._hover_day:
            return
        previous = self._hover_day
        self._hover_day = day
        if previous is not None:
            self._paint_day(previous)
        if day is not None:
            self._paint_day(day)
        self.canvas.configure(cursor="hand2" if day is not None else "")

    def _mouse_leave(self, event):
        previous = self._hover_day
        self._hover_day = None
        if previous is not None:
            self._paint_day(previous)
        self.canvas.configure(cursor="")

    def _mouse_release(self, event):
        day = self._day_at(event)
        if day is not None:
            self._select_day(day)

    def _select_day(self, day):
        previous = self.selected_day
        self.selected_day = day
        if previous in self.day_items and previous != day:
            self._paint_day(previous)
        self._paint_day(day)
        self.on_day_selected(day)

    def _mouse_wheel(self, event):
        widget = event.widget
        while widget is not self and widget.master is not None:
            widget = widget.master
        if widget is self:
            scroll = self.canvas.xview_scroll if event.state & 1 else self.canvas.yview_scroll
            scroll(-int(event.delta / 120) * 3, "units")

    def _set_scaling(self, new_widget_scaling, new_window_scaling):
        super()._set_scaling(new_widget_scaling, new_window_scaling)
        self.day_font.configure(size=-round(10 * new_widget_scaling))
        self.total_font.configure(size=-round(10 * new_widget_scaling))
        self.title_font.configure(size=-round(14 * new_widget_scaling))
        self.canvas.configure(xscrollincrement=round(20 * new_widget_scaling),
                              yscrollincrement=round(20 * new_widget_scaling))
        for orientation in ("Vertical", "Horizontal"):
            self._scroll_style.configure(f"YearExpense.{orientation}.TScrollbar",
                                         width=round(12 * new_widget_scaling))
        if self.year is not None:
            self._measure_minimum_width()
        self._layout_width = None
        self._sync_layout()

    def destroy(self):
        if self._layout_after_id is not None:
            self.after_cancel(self._layout_after_id)
            self._layout_after_id = None
        self._wheel_owner.unbind("<MouseWheel>", self._wheel_binding)
        super().destroy()
