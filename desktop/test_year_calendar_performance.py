"""年度日历不能重新引入数百个原生子窗口造成缩放阻塞。"""
import unittest

import customtkinter as ctk

from year_calendar import YearExpenseCalendar


class CalendarRenderingTests(unittest.TestCase):
    def test_full_year_uses_bounded_native_window_count(self):
        window = ctk.CTk()
        window.withdraw()
        self.addCleanup(self.close_window, window)
        control = YearExpenseCalendar(window, lambda day: None)
        control.pack(fill="both", expand=True)
        control.set_year(2025, {"2025-03-17": 28385800})
        pending = [str(control)]
        count = 0
        while pending:
            widget = pending.pop()
            count += 1
            pending.extend(window.tk.splitlist(window.tk.call("winfo", "children", widget)))
        self.assertLessEqual(count, 10,
            "全年日期应绘制在单个画布中，避免上千个子窗口在缩放时同步重绘")

    @staticmethod
    def close_window(window):
        widgets, owners = [window], {}
        while widgets:
            widget = widgets.pop()
            owners.update((command, widget) for command in widget._tclCommands or ())
            widgets.extend(widget.winfo_children())
        for callback_id in window.tk.call("after", "info"):
            script, _ = window.tk.call("after", "info", callback_id)
            if script.split()[0] in owners:
                owners[script.split()[0]].after_cancel(callback_id)
        window.destroy()


if __name__ == "__main__":
    unittest.main()
