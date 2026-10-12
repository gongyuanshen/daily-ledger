"""真实 Tk 控件与临时账本验收；对话框只模拟用户的选择。"""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import LedgerApp
from ledger import Ledger


class WindowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.ledger = Ledger(Path(self.temp.name) / "账本.sqlite3")
        self.window = LedgerApp(self.ledger)
        self.window.withdraw()
        self.window.view_day_var.set("2026-10-10")
        self.window.load_day()

    def tearDown(self):
        self.window.destroy()
        self.ledger.close()
        self.temp.cleanup()

    def enter(self, amount, day="2026-10-10", note=""):
        self.window.entry_day_var.set(day)
        self.window.amount_var.set(amount)
        self.window.note_var.set(note)
        # CTkButton.invoke 直接执行 Python；真实用户点击通过 Tk 回调进入异常处理。
        self.window.after(0, self.window.save_button.invoke)
        self.window.update()

    def select_first(self):
        item = self.window.tree.get_children()[0]
        self.window.tree.selection_set(item)
        self.window.tree.focus(item)

    def test_save_buttons_show_exact_total_and_persist_each_expense(self):
        self.enter("0.10", note="早餐")
        self.enter("0.20", note="公交")
        self.assertEqual(self.window.total_var.get(), "¥ 0.30")
        self.assertEqual(len(self.window.tree.get_children()), 2)
        self.assertEqual(self.window.amount_var.get(), "")
        self.assertEqual(len(self.ledger.list_day("2026-10-10")), 2)
        self.assertIn("保存", self.window.status_var.get())

    def test_edit_moves_expense_to_new_day_and_updates_summary(self):
        self.enter("12.30", note="午餐")
        self.select_first()
        self.window.edit_button.invoke()
        self.assertEqual(self.window.amount_var.get(), "12.30")
        self.window.entry_day_var.set("2026-10-09")
        self.window.amount_var.set("15.60")
        self.window.save_button.invoke()
        self.assertEqual(self.ledger.list_day("2026-10-10"), [])
        self.assertEqual(self.window.total_var.get(), "¥ 15.60")
        self.assertEqual(self.window.view_day_var.get(), "2026-10-09")
        self.assertEqual(len(self.ledger.list_day("2026-10-09")), 1)

    def test_cancel_edit_keeps_original_amount(self):
        self.enter("12.30")
        self.select_first()
        self.window.edit_button.invoke()
        self.window.amount_var.set("99.00")
        self.window.cancel_button.invoke()
        self.assertEqual(self.ledger.list_day("2026-10-10")[0]["amount_units"], 12300000)
        self.assertIsNone(self.window.editing_id)

    def test_edit_cancel_button_is_accessible_at_minimum_window_size(self):
        self.window.geometry("940x700+10+10")
        self.window.deiconify()
        self.window.update()
        self.enter("12.30")
        self.select_first()
        self.window.edit_button.invoke()
        self.window.update_idletasks()
        for control in (self.window.save_button, self.window.cancel_button):
            self.assertTrue(control.winfo_ismapped())
            self.assertLessEqual(control.winfo_y() + control.winfo_height(),
                                 control.master.winfo_height())

    def test_delete_cancel_and_confirm_change_only_selected_record(self):
        self.enter("10.00")
        self.enter("20.00")
        self.select_first()
        with patch("app.messagebox.askyesno", return_value=False):
            self.window.delete_button.invoke()
        self.assertEqual(len(self.ledger.list_day("2026-10-10")), 2)
        with patch("app.messagebox.askyesno", return_value=True):
            self.window.delete_button.invoke()
        self.assertEqual(self.window.total_var.get(), "¥ 10.00")
        self.assertEqual(len(self.ledger.list_day("2026-10-10")), 1)

    def test_invalid_amount_is_visible_and_retains_input(self):
        with patch("app.messagebox.showwarning") as warning:
            self.enter("1.2345678")
        warning.assert_called_once()
        self.assertEqual(self.window.amount_var.get(), "1.2345678")
        self.assertEqual(self.ledger.list_day("2026-10-10"), [])
        self.assertNotIn("已保存", self.window.status_var.get())

    def test_real_write_error_preserves_input_and_has_visible_error(self):
        self.ledger.connection.execute("PRAGMA query_only = ON")
        with patch("app.messagebox.showerror") as error:
            with self.assertLogs("ledger_app", level="ERROR") as recorded:
                self.enter("23.45", note="不能丢失这条输入")
        error.assert_called_once()
        self.assertIn("readonly", "\n".join(recorded.output))
        self.assertEqual(self.window.amount_var.get(), "23.45")
        self.assertEqual(self.window.note_var.get(), "不能丢失这条输入")
        self.assertEqual(self.ledger.list_day("2026-10-10"), [])
        self.assertNotIn("已保存", self.window.status_var.get())

    def test_committed_save_with_read_error_cannot_be_retried_as_new_expense(self):
        self.ledger.connection.set_authorizer(
            lambda action, *args: sqlite3.SQLITE_DENY
            if action == sqlite3.SQLITE_SELECT else sqlite3.SQLITE_OK)
        with patch("app.messagebox.showerror") as error:
            with self.assertLogs("ledger_app", level="ERROR"):
                self.enter("12.30", note="午餐")
        error.assert_called_once()
        self.assertEqual(self.window.amount_var.get(), "")
        self.assertIn("已保存", self.window.status_var.get())
        self.assertIn("刷新失败", self.window.status_var.get())
        self.ledger.connection.set_authorizer(None)
        self.assertEqual(len(self.ledger.list_day("2026-10-10")), 1)
        with patch("app.messagebox.showwarning"):
            self.window.save_button.invoke()
        self.assertEqual(len(self.ledger.list_day("2026-10-10")), 1)

    def test_day_query_excludes_other_dates(self):
        self.enter("8.80", "2026-10-09")
        self.enter("12.30", "2026-10-10")
        self.window.view_day_var.set("2026-10-09")
        self.window.query_button.invoke()
        self.assertEqual(self.window.total_var.get(), "¥ 8.80")
        self.assertEqual(len(self.window.tree.get_children()), 1)

    def test_invalid_query_keeps_displayed_day_and_total(self):
        self.enter("8.80")
        self.window.view_day_var.set("2026-02-30")
        with patch("app.messagebox.showwarning") as warning:
            self.window.query_button.invoke()
        warning.assert_called_once()
        self.assertEqual(self.window.total_var.get(), "¥ 8.80")
        self.assertEqual(self.window.displayed_day, "2026-10-10")

    def test_delete_refreshes_displayed_day_when_query_text_is_unsubmitted(self):
        self.enter("10.00")
        self.enter("20.00")
        self.select_first()
        self.window.view_day_var.set("2026-02-30")
        with patch("app.messagebox.askyesno", return_value=True):
            with patch("app.messagebox.showwarning"):
                self.window.delete_button.invoke()
        self.assertEqual(self.window.total_var.get(), "¥ 10.00")
        self.assertEqual(len(self.window.tree.get_children()), 1)
        self.assertEqual(self.window.view_day_var.get(), "2026-10-10")

    def test_error_hook_works_without_standard_error_stream(self):
        with patch("app.sys.stderr", None), patch("app.messagebox.showerror") as error:
            with self.assertLogs("ledger_app", level="ERROR"):
                exception = sqlite3.OperationalError("database is locked")
                self.window.report_callback_exception(type(exception), exception, None)
        error.assert_called_once()
        self.assertIn("失败", self.window.status_var.get())


if __name__ == "__main__":
    unittest.main()
