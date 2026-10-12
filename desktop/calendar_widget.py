"""可手动输入、可点击选取的日期控件。"""
import calendar
from datetime import date
import math
import re
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from ledger import parse_day


ACCENT = "#6C5CE7"
ACCENT_HOVER = "#5848CF"
TEXT = "#263149"
MUTED = "#8290A7"
BORDER = "#E5E8F0"
FONT = ("Microsoft YaHei UI", 13)


class CalendarDateEntry(ctk.CTkFrame):
    def __init__(self, master, variable: tk.StringVar, command=None, width=160, **kwargs):
        super().__init__(master, width=width, fg_color="white", corner_radius=8,
                         border_width=1, border_color=BORDER, **kwargs)
        self.variable = variable
        self.command = command
        self.popup = None
        self.grid_columnconfigure(0, weight=1)
        self.entry = ctk.CTkEntry(
            self, textvariable=variable, width=width - 45, height=36,
            border_width=0, fg_color="white", text_color=TEXT,
            font=FONT, corner_radius=8)
        self.entry.grid(row=0, column=0, padx=(4, 0), pady=1, sticky="ew")
        self.entry.bind("<Button-1>", lambda event: self.open_calendar())
        if command is not None:
            self.entry.bind("<Return>", lambda event: command())
        self.calendar_button = ctk.CTkButton(
            self, text="▦", width=34, height=30, font=("Segoe UI Symbol", 20),
            fg_color=ACCENT, hover_color=ACCENT_HOVER, corner_radius=7,
            command=self.open_calendar)
        self.calendar_button.grid(row=0, column=1, padx=4, pady=4)

    def open_calendar(self):
        try:
            value = date.fromisoformat(parse_day(self.variable.get()))
        except ValueError as error:
            messagebox.showwarning("日期无效", str(error), parent=self.winfo_toplevel())
            return None
        if self.popup is not None and self.popup.winfo_exists():
            self.popup.lift()
            self.popup.focus_force()
            return self.popup
        self.popup = CalendarPopup(self, value, self._select_date)
        return self.popup

    def _select_date(self, value):
        self.variable.set(value.isoformat())
        if self.command is not None:
            self.command()


class CalendarPopup(ctk.CTkToplevel):
    def __init__(self, owner, value: date, on_select):
        super().__init__(owner)
        self.withdraw()
        self.title("选择日期")
        self.configure(fg_color="white")
        self.resizable(False, False)
        self.transient(owner.winfo_toplevel())
        self.bind("<Escape>", lambda event: self.destroy())
        self.selected_date = value
        self.year, self.month = value.year, value.month
        self.on_select = on_select
        self.year_var = tk.StringVar(self, str(self.year))
        self.month_var = tk.StringVar(self, f"{self.month}月")

        header = ctk.CTkFrame(self, fg_color="white")
        header.pack(fill="x", padx=16, pady=(16, 8))
        header.grid_columnconfigure(1, weight=1)
        self.previous_button = ctk.CTkButton(
            header, text="‹", width=32, height=32, font=("Segoe UI", 22),
            fg_color="#F3F4FA", text_color=TEXT, hover_color=BORDER,
            corner_radius=8, command=lambda: self._change_month(-1))
        self.previous_button.grid(row=0, column=0)
        self.month_title = ctk.CTkLabel(header, text="", font=(FONT[0], 16, "bold"),
                                        text_color=TEXT)
        self.month_title.grid(row=0, column=1, padx=8)
        self.next_button = ctk.CTkButton(
            header, text="›", width=32, height=32, font=("Segoe UI", 22),
            fg_color="#F3F4FA", text_color=TEXT, hover_color=BORDER,
            corner_radius=8, command=lambda: self._change_month(1))
        self.next_button.grid(row=0, column=2)

        selectors = ctk.CTkFrame(self, fg_color="white")
        selectors.pack(fill="x", padx=16, pady=(0, 8))
        self.year_entry = ctk.CTkEntry(
            selectors, textvariable=self.year_var, width=75, height=30,
            font=FONT, fg_color="white", text_color=TEXT,
            border_color=BORDER, corner_radius=8)
        self.year_entry.pack(side="left")
        self.year_entry.bind("<Return>", lambda event: self._apply_year())
        ctk.CTkLabel(selectors, text="年", font=FONT, text_color=MUTED,
                     width=24).pack(side="left")
        self.month_menu = ctk.CTkOptionMenu(
            selectors, variable=self.month_var,
            values=[f"{month}月" for month in range(1, 13)],
            command=self._select_month, width=82, height=30, font=FONT,
            dropdown_font=FONT, fg_color="#F3F4FA", button_color="#F3F4FA",
            button_hover_color=BORDER, text_color=TEXT,
            dropdown_fg_color="white", dropdown_text_color=TEXT,
            dropdown_hover_color=BORDER, corner_radius=8)
        self.month_menu.pack(side="left", padx=(0, 8))
        self.year_apply_button = ctk.CTkButton(
            selectors, text="跳转", width=65, height=30, font=FONT,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            corner_radius=8, command=self._apply_year)
        self.year_apply_button.pack(side="right")

        weekdays = ctk.CTkFrame(self, fg_color="white")
        weekdays.pack(fill="x", padx=16)
        for column, name in enumerate("一二三四五六日"):
            weekdays.grid_columnconfigure(column, weight=1, uniform="weekdays")
            ctk.CTkLabel(weekdays, text=name, font=FONT, text_color=MUTED,
                         width=34, height=28).grid(row=0, column=column, sticky="ew")
        self.days_frame = ctk.CTkFrame(self, fg_color="white", height=204)
        self.days_frame.pack(fill="x", padx=16)
        self.days_frame.grid_propagate(False)
        for column in range(7):
            self.days_frame.grid_columnconfigure(column, weight=1, uniform="days")

        footer = ctk.CTkFrame(self, fg_color="white")
        footer.pack(fill="x", padx=16, pady=(8, 16))
        self.today_button = ctk.CTkButton(
            footer, text="今天", width=110, height=32, font=FONT,
            fg_color=ACCENT, hover_color=ACCENT_HOVER, corner_radius=8,
            command=lambda: self._choose_date(date.today()))
        self.today_button.pack(side="left")
        self.cancel_button = ctk.CTkButton(
            footer, text="取消", width=110, height=32, font=FONT,
            fg_color="#F3F4FA", hover_color=BORDER, text_color=TEXT,
            corner_radius=8, command=self.destroy)
        self.cancel_button.pack(side="right")
        self._render_month()
        self.update_idletasks()
        # CTk.geometry 接受未缩放尺寸，Tk.winfo_* 返回实际屏幕像素。
        height = math.ceil(self.winfo_reqheight() / self._get_window_scaling())
        self.geometry(f"310x{height}")
        self.deiconify()
        self.update_idletasks()
        border_x = self.winfo_rootx() - self.winfo_x()
        border_y = self.winfo_rooty() - self.winfo_y()
        x = min(max(owner.winfo_rootx(), 8),
                self.winfo_screenwidth() - self.winfo_width() - border_x - 8)
        y = owner.winfo_rooty() + owner.winfo_height() + 6
        y = min(max(y, 8),
                self.winfo_screenheight() - self.winfo_height() - border_y - 8)
        self.geometry(f"+{x}+{y}")
        self.grab_set()
        self.focus_force()

    def _render_month(self):
        self.month_title.configure(text=f"{self.year}年{self.month}月")
        self.year_var.set(str(self.year))
        self.month_var.set(f"{self.month}月")
        self.previous_button.configure(
            state="disabled" if (self.year, self.month) == (1, 1) else "normal")
        self.next_button.configure(
            state="disabled" if (self.year, self.month) == (9999, 12) else "normal")
        for widget in self.days_frame.winfo_children():
            widget.destroy()
        self.day_buttons = {}
        today = date.today()
        for row, week in enumerate(calendar.Calendar(firstweekday=0).monthdayscalendar(
                self.year, self.month)):
            for column, day in enumerate(week):
                if day == 0:
                    continue
                value = date(self.year, self.month, day)
                selected = value == self.selected_date
                button = ctk.CTkButton(
                    self.days_frame, text=str(day), width=34, height=30,
                    font=FONT, corner_radius=8, border_width=1 if value == today else 0,
                    border_color=ACCENT, fg_color=ACCENT if selected else "white",
                    text_color="white" if selected else TEXT,
                    hover_color=ACCENT_HOVER if selected else "#F0EDFF",
                    command=lambda value=value: self._choose_date(value))
                button.grid(row=row, column=column, padx=1, pady=2, sticky="ew")
                self.day_buttons[day] = button

    def _change_month(self, step):
        year, month = divmod((self.year - 1) * 12 + self.month - 1 + step, 12)
        self.year, self.month = year + 1, month + 1
        self._render_month()

    def _select_month(self, value):
        self.month = int(value[:-1])
        self._render_month()

    def _apply_year(self):
        text = self.year_var.get().strip()
        if not re.fullmatch(r"[0-9]{1,4}", text) or not 1 <= int(text) <= 9999:
            messagebox.showwarning("年份无效", "请输入 1 至 9999 之间的年份。", parent=self)
            return
        self.year = int(text)
        self._render_month()

    def _choose_date(self, value):
        self.destroy()
        self.on_select(value)

    def destroy(self):
        # CTk 的标题栏、焦点与图标回调归该窗口所有；Tk.destroy 只删除
        # Tcl command，不取消 after，必须在 command 销毁前释放这些计时器。
        widgets = [self]
        command_owners = {}
        while widgets:
            widget = widgets.pop()
            command_owners.update((command, widget) for command in widget._tclCommands or ())
            widgets.extend(widget.winfo_children())
        for callback_id in self.tk.call("after", "info"):
            script, _ = self.tk.call("after", "info", callback_id)
            command = script.split()[0]
            if command in command_owners:
                command_owners[command].after_cancel(callback_id)
        super().destroy()
