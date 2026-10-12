"""日期选择器的真实 Tk 控件验收；仅替代阻塞式警告对话框。"""
from datetime import date
import tkinter as tk
import unittest
from unittest.mock import patch

import customtkinter as ctk

from calendar_widget import CalendarDateEntry


class CalendarWidgetTests(unittest.TestCase):
    def setUp(self):
        ctk.set_appearance_mode("light")
        self.window = ctk.CTk()
        self.window.geometry("400x220+50+50")
        self.variable = tk.StringVar(self.window, "2024-02-10")
        self.selected = []
        self.control = CalendarDateEntry(
            self.window, self.variable,
            command=lambda: self.selected.append(self.variable.get()))
        self.control.pack(padx=20, pady=20)
        self.window.update()

    def tearDown(self):
        self.window.update_idletasks()
        # 每个用例独占一个 Tcl 解释器，由注册计时器的控件释放资源。
        widgets = [self.window]
        command_owners = {}
        while widgets:
            widget = widgets.pop()
            command_owners.update((command, widget) for command in widget._tclCommands or ())
            widgets.extend(widget.winfo_children())
        for callback_id in self.window.tk.call("after", "info"):
            script, _ = self.window.tk.call("after", "info", callback_id)
            command_owners[script.split()[0]].after_cancel(callback_id)
        self.window.destroy()

    def open_popup(self):
        self.control.calendar_button.invoke()
        self.window.update()
        return self.control.popup

    def test_leap_february_places_days_under_correct_weekday(self):
        popup = self.open_popup()
        self.assertEqual(set(popup.day_buttons), set(range(1, 30)))
        self.assertEqual(popup.day_buttons[1].grid_info()["column"], 3)
        self.assertEqual(popup.day_buttons[29].grid_info()["column"], 3)
        self.assertNotEqual(popup.day_buttons[10].cget("fg_color"),
                            popup.day_buttons[11].cget("fg_color"))

    def test_selecting_day_updates_iso_date_and_calls_owner_once(self):
        popup = self.open_popup()
        popup.day_buttons[29].invoke()
        self.assertEqual(self.variable.get(), "2024-02-29")
        self.assertEqual(self.selected, ["2024-02-29"])
        self.assertFalse(popup.winfo_exists())

    def test_month_navigation_crosses_year_and_keeps_original_until_selected(self):
        self.variable.set("2025-12-31")
        popup = self.open_popup()
        popup.next_button.invoke()
        self.assertEqual((popup.year, popup.month), (2026, 1))
        self.assertEqual(self.variable.get(), "2025-12-31")
        popup.previous_button.invoke()
        self.assertEqual((popup.year, popup.month), (2025, 12))

    def test_year_and_month_controls_jump_to_nonleap_february(self):
        popup = self.open_popup()
        popup.year_var.set("2025")
        popup.year_apply_button.invoke()
        self.assertEqual((popup.year, popup.month), (2025, 2))
        self.assertEqual(set(popup.day_buttons), set(range(1, 29)))
        popup.month_menu._dropdown_menu.invoke(11)
        self.assertEqual((popup.year, popup.month), (2025, 12))
        popup.day_buttons[31].invoke()
        self.assertEqual(self.variable.get(), "2025-12-31")

    def test_cancel_preserves_date_after_navigation(self):
        popup = self.open_popup()
        popup.next_button.invoke()
        popup.cancel_button.invoke()
        self.assertEqual(self.variable.get(), "2024-02-10")
        self.assertEqual(self.selected, [])
        self.assertFalse(popup.winfo_exists())

    def test_escape_closes_calendar_without_changing_date(self):
        popup = self.open_popup()
        popup.event_generate("<Escape>")
        self.window.update()
        self.assertFalse(popup.winfo_exists())
        self.assertEqual(self.variable.get(), "2024-02-10")
        self.assertEqual(self.selected, [])

    def test_popup_remains_inside_screen_near_bottom_right(self):
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        self.window.geometry(f"400x220+{screen_width - 40}+{screen_height - 40}")
        self.window.update()
        popup = self.open_popup()
        self.assertGreaterEqual(popup.winfo_rootx(), 0)
        self.assertGreaterEqual(popup.winfo_rooty(), 0)
        self.assertLessEqual(popup.winfo_rootx() + popup.winfo_width(), screen_width)
        self.assertLessEqual(popup.winfo_rooty() + popup.winfo_height(), screen_height)

    def test_today_selects_real_current_date(self):
        popup = self.open_popup()
        popup.today_button.invoke()
        self.assertEqual(self.variable.get(), date.today().isoformat())
        self.assertEqual(self.selected, [date.today().isoformat()])

    def test_repeated_open_reuses_popup_and_can_reopen_after_close(self):
        popup = self.open_popup()
        self.assertIs(self.control.open_calendar(), popup)
        popup.cancel_button.invoke()
        reopened = self.control.open_calendar()
        self.assertIsNot(reopened, popup)
        self.assertTrue(reopened.winfo_exists())

    def test_closing_popup_releases_its_scheduled_tk_callbacks(self):
        self.window.tk.eval("set ::calendar_background_errors {}")
        self.window.tk.eval(
            "proc bgerror {message} {lappend ::calendar_background_errors $message}")
        popup = self.open_popup()
        popup.cancel_button.invoke()
        self.window.after(300, self.window.quit)
        self.window.mainloop()
        self.assertEqual(self.window.tk.eval("set ::calendar_background_errors"), "")

    def test_invalid_existing_date_warns_without_substituting_today(self):
        for invalid in ("2026-02-30", "20261010", ""):
            with self.subTest(invalid=invalid):
                self.variable.set(invalid)
                with patch("calendar_widget.messagebox.showwarning") as warning:
                    self.assertIsNone(self.control.open_calendar())
                warning.assert_called_once()
                self.assertIsNone(self.control.popup)
                self.assertEqual(self.variable.get(), invalid)
                self.assertEqual(self.selected, [])

    def test_input_can_be_typed_and_clicked_to_open_calendar(self):
        self.control.entry.delete(0, "end")
        self.control.entry.insert(0, "2026-10-10")
        self.assertEqual(self.variable.get(), "2026-10-10")
        self.control.entry._entry.event_generate("<Button-1>")
        self.window.update()
        self.assertEqual((self.control.popup.year, self.control.popup.month), (2026, 10))

    def test_return_submits_manually_entered_date(self):
        self.control.entry._entry.focus_force()
        self.variable.set("2026-09-01")
        self.control.entry._entry.event_generate("<Return>")
        self.window.update()
        self.assertEqual(self.selected, ["2026-09-01"])

    def test_year_bounds_disable_navigation_and_reject_invalid_year(self):
        self.variable.set("0001-01-01")
        popup = self.open_popup()
        self.assertEqual(popup.previous_button.cget("state"), "disabled")
        popup.previous_button.invoke()
        self.assertEqual((popup.year, popup.month), (1, 1))
        popup.year_var.set("9999")
        popup.year_apply_button.invoke()
        popup.month_menu._dropdown_menu.invoke(11)
        self.assertEqual(popup.next_button.cget("state"), "disabled")
        popup.next_button.invoke()
        self.assertEqual((popup.year, popup.month), (9999, 12))
        for invalid in ("0", "10000", "year"):
            with self.subTest(invalid=invalid):
                popup.year_var.set(invalid)
                with patch("calendar_widget.messagebox.showwarning") as warning:
                    popup.year_apply_button.invoke()
                warning.assert_called_once()
                self.assertEqual((popup.year, popup.month), (9999, 12))
                self.assertEqual(popup.year_var.get(), invalid)
        self.assertEqual(self.variable.get(), "0001-01-01")


if __name__ == "__main__":
    unittest.main()
