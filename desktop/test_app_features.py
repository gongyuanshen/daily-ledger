import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import LedgerApp
from ledger import Ledger


class FeatureWindowTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.ledger = Ledger(Path(self.directory.name) / "ledger.sqlite3")
        self.addCleanup(self.ledger.close)
        self.window = LedgerApp(self.ledger)
        self.window.withdraw()
        self.addCleanup(self.window.destroy)

    def enter(self, amount, day, category, payment, note=""):
        self.window.entry_day_var.set(day)
        self.window.amount_var.set(amount)
        self.window.category_var.set(category)
        self.window.payment_var.set(payment)
        self.window.note_var.set(note)
        self.window.save_button.invoke()

    def test_high_precision_input_and_zero_day_keep_exact_value(self):
        with patch("app.messagebox.showwarning"):
            self.enter("33.662720", "2026-10-10", "未分类", "未指定", "历史日汇总")
        self.assertEqual(len(self.ledger.list_entries()), 1)
        row = self.ledger.list_entries()[0]
        self.assertEqual(row["amount_units"], 33662720)
        self.assertEqual(self.window.total_var.get(), "¥ 33.66272")
        self.window.tree.selection_set(self.window.tree.get_children()[0])
        self.window.edit_selected()
        self.assertEqual(self.window.amount_var.get(), "33.66272")
        self.window.amount_var.set("45.986")
        self.window.save_button.invoke()
        self.assertEqual(self.ledger.list_entries()[0]["amount_units"], 45986000)
        self.enter("0", "2026-10-11", "未分类", "未指定", "原文明确零支出")
        self.window.report_day_var.set("2026-10-10")
        self.window.refresh_reports()
        self.assertEqual(self.window.report_total_var.get(), "¥ 45.986")

    def test_zero_only_month_chart_is_valid_and_zero_budget_is_rejected(self):
        with patch("app.messagebox.showwarning"):
            self.enter("0", "2026-10-10", "未分类", "未指定")
        self.assertEqual(len(self.ledger.list_entries()), 1)
        self.window.report_day_var.set("2026-10-10")
        self.window.show_page("统计分析")
        self.window.deiconify()
        self.window.update()
        self.window.draw_trend()
        self.assertEqual(self.window.report_total_var.get(), "¥ 0.00")
        self.window.budget_day_var.set("2026-10-10")
        self.window.budget_amount_var.set("0")
        with patch("app.messagebox.showwarning") as warning:
            self.window.save_budget()
        warning.assert_called_once()
        self.assertIsNone(self.ledger.get_budget("2026-10"))

    def test_form_saves_and_edits_category_and_payment(self):
        self.enter("28.50", "2026-10-10", "餐饮", "微信", "午餐")
        row = self.ledger.list_entries()[0]
        self.assertEqual((row["category"], row["payment"]), ("餐饮", "微信"))
        item = self.window.tree.get_children()[0]
        self.window.tree.selection_set(item)
        self.window.edit_button.invoke()
        self.assertEqual(self.window.category_var.get(), "餐饮")
        self.window.category_var.set("交通")
        self.window.payment_var.set("现金")
        self.window.save_button.invoke()
        row = self.ledger.list_entries()[0]
        self.assertEqual((row["category"], row["payment"]), ("交通", "现金"))

    def test_range_category_and_keyword_filters_match_displayed_total(self):
        self.enter("10.00", "2026-10-09", "餐饮", "微信", "午餐")
        self.enter("20.00", "2026-10-10", "餐饮", "支付宝", "晚餐")
        self.enter("30.00", "2026-10-10", "交通", "微信", "公交")
        self.window.period_var.set("自定义")
        self.window.range_start_var.set("2026-10-09")
        self.window.range_end_var.set("2026-10-10")
        self.window.filter_category_var.set("餐饮")
        self.window.keyword_var.set("晚餐")
        self.window.query_button.invoke()
        self.assertEqual(self.window.total_var.get(), "¥ 20.00")
        self.assertEqual(len(self.window.tree.get_children()), 1)

    def test_reversed_range_is_rejected_without_changing_results(self):
        self.enter("10.00", "2026-10-10", "未分类", "未指定")
        self.window.period_var.set("自定义")
        self.window.range_start_var.set("2026-10-11")
        self.window.range_end_var.set("2026-10-09")
        with patch("app.messagebox.showwarning") as warning:
            self.window.query_button.invoke()
        warning.assert_called_once()
        self.assertEqual(self.window.total_var.get(), "¥ 10.00")

    def test_invalid_custom_range_remains_visible_for_correction(self):
        self.window.period_var.set("自定义")
        self.window.apply_filters()
        self.window.range_start_var.set("2026-10-11")
        self.window.range_end_var.set("2026-10-09")
        self.window.period_var.set("全部")
        self.window.apply_filters()
        self.window.period_var.set("自定义")
        with patch("app.messagebox.showwarning"):
            self.window.apply_filters()
        self.assertTrue(self.window.range_frame.grid_info())

    def test_new_expense_button_exits_edit_mode_without_changing_record(self):
        self.enter("10.00", "2026-10-10", "餐饮", "现金")
        self.window.tree.selection_set(self.window.tree.get_children()[0])
        self.window.edit_selected()
        self.window.focus_form()
        self.assertIsNone(self.window.editing_id)
        self.assertEqual(self.window.amount_var.get(), "")
        self.assertEqual(self.ledger.list_entries()[0]["amount_units"], 10000000)

    def test_all_pages_fit_minimum_window_and_summary_is_ledger_only(self):
        self.window.geometry("1120x740+10+10")
        self.window.deiconify()
        for name in self.window.pages:
            self.window.show_page(name)
            self.window.update()
            page = self.window.pages[name]
            self.assertTrue(page.winfo_ismapped())
            self.assertEqual(self.window.overview.winfo_ismapped(), name == "账本明细")
            self.assertLessEqual(page.winfo_rooty() + page.winfo_height(),
                                 self.window.winfo_rooty() + self.window.winfo_height())

    def test_amount_sort_is_numeric(self):
        self.enter("2.00", "2026-10-10", "未分类", "未指定")
        self.enter("10.00", "2026-10-10", "未分类", "未指定")
        self.window.sort_table("amount_units")
        values = [self.window.tree.item(item, "values")[3]
                  for item in self.window.tree.get_children()]
        self.assertEqual(values, ["2.00", "10.00"])

    def test_reports_use_selected_month(self):
        self.enter("10.10", "2026-10-10", "餐饮", "微信")
        self.enter("20.20", "2026-10-11", "交通", "现金")
        self.enter("90.00", "2026-09-01", "其他", "现金")
        self.window.report_day_var.set("2026-10-10")
        self.window.refresh_reports()
        self.assertEqual(self.window.report_total_var.get(), "¥ 30.30")
        self.assertEqual(self.window.chart_data["by_day"]["2026-10-11"], 20200000)

    def test_chart_resize_uses_loaded_month_instead_of_unsubmitted_date(self):
        self.enter("10.00", "2026-10-10", "餐饮", "微信")
        self.window.report_day_var.set("2026-10-10")
        self.window.show_page("统计分析")
        self.window.deiconify()
        self.window.update()
        before = [self.window.trend_canvas.coords(item)
                  for item in self.window.trend_canvas.find_all()]
        self.window.report_day_var.set("invalid date")
        self.window.draw_trend()
        after = [self.window.trend_canvas.coords(item)
                 for item in self.window.trend_canvas.find_all()]
        self.assertEqual(after, before)
        self.window.report_day_var.set("2026-09-01")
        self.window.draw_trend()
        self.assertEqual([self.window.trend_canvas.coords(item)
                          for item in self.window.trend_canvas.find_all()], before)

    def test_budget_is_saved_and_overage_is_shown(self):
        self.enter("125.50", "2026-10-10", "餐饮", "微信")
        self.window.budget_day_var.set("2026-10-10")
        self.window.budget_amount_var.set("100.00")
        self.window.budget_save_button.invoke()
        self.assertEqual(self.ledger.get_budget("2026-10"), 100000000)
        self.assertIn("超出", self.window.budget_remaining_var.get())
        self.assertIn("25.50", self.window.budget_remaining_var.get())

    def test_export_button_writes_current_filtered_records(self):
        self.enter("10.00", "2026-10-09", "餐饮", "微信")
        self.enter("20.00", "2026-10-10", "交通", "现金")
        destination = Path(self.directory.name) / "export.csv"
        with patch("app.filedialog.asksaveasfilename", return_value=str(destination)):
            self.window.export_current()
        with destination.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.reader(handle))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][:4], ["2026-10-10", "20.00", "交通", "现金"])

    def test_backup_and_restore_preserve_existing_records(self):
        self.enter("10.00", "2026-10-10", "餐饮", "微信")
        destination = Path(self.directory.name) / "backup.sqlite3"
        with patch("app.filedialog.asksaveasfilename", return_value=str(destination)):
            self.window.backup_ledger()
        self.enter("20.00", "2026-10-10", "交通", "现金")
        with patch("app.filedialog.askopenfilename", return_value=str(destination)), \
             patch("app.messagebox.askyesno", return_value=True):
            self.window.restore_ledger()
        self.assertEqual(len(self.ledger.list_entries()), 1)
        self.assertIsNone(self.window.editing_id)
        self.assertTrue(list((self.ledger.path.parent / "backups").glob("before-restore-*.sqlite3")))

    def test_restore_refreshes_custom_category_and_payment_choices(self):
        source = Path(self.directory.name) / "other.sqlite3"
        other = Ledger(source)
        other.add("2026-10-10", 10000000, "", "宠物", "信用卡")
        other.close()
        with patch("app.filedialog.askopenfilename", return_value=str(source)), \
             patch("app.messagebox.askyesno", return_value=True):
            self.window.restore_ledger()
        self.assertIn("宠物", self.window.category_entry.cget("values"))
        self.assertIn("宠物", self.window.filter_category.cget("values"))
        self.assertIn("信用卡", self.window.payment_entry.cget("values"))
        self.assertIn("信用卡", self.window.filter_payment.cget("values"))

    def test_restore_replaces_stale_rows_when_date_text_is_unsubmitted(self):
        self.enter("1.00", "2026-10-10", "餐饮", "现金", "旧记录")
        source = Path(self.directory.name) / "other.sqlite3"
        other = Ledger(source)
        other.add("2026-10-10", 99000000, "恢复记录", "其他", "微信")
        other.close()
        self.window.view_day_var.set("bad-date")
        with patch("app.filedialog.askopenfilename", return_value=str(source)), \
             patch("app.messagebox.askyesno", return_value=True), \
             patch("app.messagebox.showwarning"):
            self.window.restore_ledger()
        self.assertEqual([row["note"] for row in self.window.entries.values()], ["恢复记录"])

    def test_restore_read_error_clears_stale_editable_ids_and_reports_commit(self):
        self.enter("1.00", "2026-10-10", "餐饮", "现金", "旧记录")
        source = Path(self.directory.name) / "other.sqlite3"
        other = Ledger(source)
        other.add("2026-10-10", 99000000, "恢复记录", "其他", "微信")
        other.close()
        # 恢复验证查询正常；只在 UI 开始读取恢复后的明细时拒绝 SELECT。
        original_restore = self.ledger.restore
        def restore_then_deny_read(path):
            original_restore(path)
            self.ledger.connection.set_authorizer(
                lambda action, *args: sqlite3.SQLITE_DENY
                if action == sqlite3.SQLITE_SELECT else sqlite3.SQLITE_OK)
        with patch.object(self.ledger, "restore", side_effect=restore_then_deny_read), \
             patch("app.filedialog.askopenfilename", return_value=str(source)), \
             patch("app.messagebox.askyesno", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "已恢复.*刷新失败"):
                self.window.restore_ledger()
        self.ledger.connection.set_authorizer(None)
        self.assertEqual(self.window.entries, {})
        self.assertEqual(self.window.tree.get_children(), ())
        self.assertEqual(self.ledger.list_entries()[0]["note"], "恢复记录")

    def test_budget_read_error_reports_successful_commit(self):
        self.window.budget_day_var.set("2026-10-10")
        self.window.budget_amount_var.set("123.45")
        self.ledger.connection.set_authorizer(
            lambda action, *args: sqlite3.SQLITE_DENY
            if action == sqlite3.SQLITE_SELECT else sqlite3.SQLITE_OK)
        with self.assertRaisesRegex(RuntimeError, "已保存.*刷新失败"):
            self.window.save_budget()
        self.ledger.connection.set_authorizer(None)
        self.assertEqual(self.ledger.get_budget("2026-10"), 123450000)


if __name__ == "__main__":
    unittest.main()
