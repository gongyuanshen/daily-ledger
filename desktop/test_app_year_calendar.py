"""年度日历到真实账本查询的窗口集成测试。"""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import LedgerApp
from ledger import Ledger, parse_amount


class YearCalendarWindowTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.ledger = Ledger(Path(directory.name) / "ledger.sqlite3")
        self.addCleanup(self.ledger.close)
        self.window = LedgerApp(self.ledger)
        self.window.withdraw()
        self.addCleanup(self.window.destroy)

    def open_year(self, year):
        self.window.nav_buttons["支出日历"].invoke()
        self.window.calendar_year_var.set(str(year))
        self.window.calendar_query_button.invoke()

    def day_text(self, day):
        calendar = self.window.year_calendar
        _, number, amount = calendar.day_items[day]
        return (calendar.canvas.itemcget(number, "text"),
                calendar.canvas.itemcget(amount, "text"))

    def test_sidebar_calendar_aggregates_real_rows_with_exact_precision(self):
        self.ledger.add("2024-02-29", parse_amount("33.66272"), "甲")
        self.ledger.add("2024-02-29", parse_amount("0.000001"), "乙")
        self.ledger.add("2024-03-01", 0, "明确零支出")
        self.ledger.add("2025-02-28", parse_amount("999"), "其他年份")
        self.open_year(2024)
        self.assertEqual(self.window.page_title_var.get(), "支出日历")
        self.assertEqual(len(self.window.year_calendar.month_items), 12)
        self.assertEqual(len(self.window.year_calendar.day_items), 366)
        self.assertEqual(self.window.calendar_total_var.get(), "¥ 33.662721")
        self.assertEqual(self.window.calendar_count_var.get(), "3 笔 · 2 个记账日")
        self.assertEqual(self.day_text("2024-02-29"), ("29", "33.662721"))
        self.assertEqual(self.day_text("2024-03-01"), ("1", "0.00"))
        self.assertEqual(self.day_text("2024-03-02"), ("2", "—"))

    def test_click_date_opens_all_daily_rows_and_preserves_form_draft(self):
        first = self.ledger.add("2024-02-29", parse_amount("12.50"), "甲", "餐饮", "微信")
        second = self.ledger.add("2024-02-29", parse_amount("6.866"), "乙", "交通", "现金")
        self.window.amount_var.set("88.123")
        self.window.note_var.set("尚未保存")
        self.window.entry_day_var.set("2026-10-10")
        self.window.filter_category_var.set("餐饮")
        self.window.filter_payment_var.set("微信")
        self.window.keyword_var.set("不存在")
        self.open_year(2024)
        self.window.year_calendar._select_day("2024-02-29")
        self.assertEqual(self.window.page_title_var.get(), "账本明细")
        self.assertEqual(self.window.period_var.get(), "当天")
        self.assertEqual(self.window.view_day_var.get(), "2024-02-29")
        self.assertEqual(set(self.window.entries), {str(first), str(second)})
        self.assertEqual(self.window.total_var.get(), "¥ 19.366")
        self.assertEqual(self.window.filter_category_var.get(), "全部分类")
        self.assertEqual(self.window.filter_payment_var.get(), "全部方式")
        self.assertEqual(self.window.keyword_var.get(), "")
        self.assertEqual(self.window.amount_var.get(), "88.123")
        self.assertEqual(self.window.note_var.get(), "尚未保存")
        self.assertEqual(self.window.entry_day_var.get(), "2026-10-10")
        self.window.nav_buttons["支出日历"].invoke()
        self.window.year_calendar._select_day("2024-03-02")
        self.assertEqual(self.window.total_var.get(), "¥ 0.00")
        self.assertEqual(len(self.window.entries), 0)

    def test_canvas_mouse_event_opens_daily_records_after_scrolling(self):
        identifier = self.ledger.add("2024-12-31", parse_amount("6.866"), "年末支出")
        self.open_year(2024)
        self.window.deiconify()
        self.window.update()
        calendar = self.window.year_calendar
        canvas = calendar.canvas
        x0, y0, x1, y1 = calendar.day_bounds["2024-12-31"]
        center_x, center_y = (x0 + x1) / 2, (y0 + y1) / 2
        left, top, right, bottom = map(float, canvas.tk.splitlist(canvas.cget("scrollregion")))
        canvas.xview_moveto(max(0, (center_x - left - canvas.winfo_width() / 2) / (right - left)))
        canvas.yview_moveto(max(0, (center_y - top - canvas.winfo_height() / 2) / (bottom - top)))
        self.window.update()
        x = round(center_x - canvas.canvasx(0))
        y = round(center_y - canvas.canvasy(0))
        self.assertGreaterEqual(x, 0)
        self.assertLess(x, canvas.winfo_width())
        self.assertGreaterEqual(y, 0)
        self.assertLess(y, canvas.winfo_height())
        self.assertGreater(canvas.yview()[0], 0)
        canvas.event_generate("<Button-1>", x=x, y=y)
        canvas.event_generate("<ButtonRelease-1>", x=x, y=y)
        self.window.update()
        self.assertEqual(self.window.page_title_var.get(), "账本明细")
        self.assertEqual(self.window.view_day_var.get(), "2024-12-31")
        self.assertEqual(set(self.window.entries), {str(identifier)})
        self.assertEqual(self.window.total_var.get(), "¥ 6.866")

    def test_invalid_year_is_visible_and_leaves_loaded_calendar_unchanged(self):
        self.open_year(2024)
        original = tuple(self.window.year_calendar.day_items["2024-02-29"])
        for value in ("invalid date", "2024.0", "0", "10000", "２０２４"):
            with self.subTest(year=value), patch("app.messagebox.showwarning") as warning:
                self.window.calendar_year_var.set(value)
                self.window.calendar_query_button.invoke()
                warning.assert_called_once()
                self.assertEqual(self.window.calendar_year, 2024)
                self.assertEqual(self.window.year_calendar.day_items["2024-02-29"], original)
                for item in original:
                    self.assertTrue(self.window.year_calendar.canvas.type(item))

    def test_year_navigation_and_boundaries(self):
        self.open_year(2024)
        self.window.calendar_next_button.invoke()
        self.assertEqual(self.window.calendar_year, 2025)
        self.assertNotIn("2025-02-29", self.window.year_calendar.day_items)
        self.window.calendar_previous_button.invoke()
        self.assertEqual(self.window.calendar_year, 2024)
        self.window.calendar_year_var.set("1")
        self.window.calendar_query_button.invoke()
        self.assertEqual(self.window.calendar_previous_button.cget("state"), "disabled")
        self.window.calendar_year_var.set("9999")
        self.window.calendar_query_button.invoke()
        self.assertEqual(self.window.calendar_next_button.cget("state"), "disabled")

    def test_reopening_calendar_reads_committed_add_edit_delete(self):
        self.open_year(2024)
        record = self.ledger.add("2024-02-29", parse_amount("45.986"), "导入")
        self.window.show_page("账本明细")
        self.window.nav_buttons["支出日历"].invoke()
        self.assertEqual(self.day_text("2024-02-29"), ("29", "45.986"))
        self.ledger.update(record, "2024-02-29", 0, "改为零")
        self.window.nav_buttons["支出日历"].invoke()
        self.assertEqual(self.day_text("2024-02-29"), ("29", "0.00"))
        self.ledger.delete(record)
        self.window.nav_buttons["支出日历"].invoke()
        self.assertEqual(self.day_text("2024-02-29"), ("29", "—"))

    def test_database_read_failure_is_exposed_before_calendar_replacement(self):
        self.open_year(2024)
        original = tuple(self.window.year_calendar.day_items["2024-02-29"])
        self.window.calendar_year_var.set("2025")
        self.ledger.connection.set_authorizer(lambda action, *args:
            sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_SELECT else sqlite3.SQLITE_OK)
        try:
            with self.assertRaises(sqlite3.DatabaseError):
                self.window.refresh_calendar()
        finally:
            self.ledger.connection.set_authorizer(None)
        self.assertEqual(self.window.calendar_year, 2024)
        self.assertEqual(self.window.year_calendar.day_items["2024-02-29"], original)
        for item in original:
            self.assertTrue(self.window.year_calendar.canvas.type(item))


if __name__ == "__main__":
    unittest.main()
