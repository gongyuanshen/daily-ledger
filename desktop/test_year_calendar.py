"""单画布年度日历的真实文本、布局、点击与生命周期验收。"""
from datetime import date
import unittest
import customtkinter as ctk
from year_calendar import ACCENT, YearExpenseCalendar


class YearCalendarTests(unittest.TestCase):
    def setUp(self):
        ctk.set_appearance_mode("light")
        self.window = ctk.CTk()
        self.window.geometry("904x640+40+40")
        self.selected = []
        self.control = YearExpenseCalendar(self.window, self.selected.append)
        self.control.pack(fill="both", expand=True)

    def tearDown(self):
        self.control.destroy()
        for callback_id in self.window.tk.call("after", "info"):
            self.window.after_cancel(callback_id)
        self.window.destroy()

    def day_text(self, day):
        _, number, amount = self.control.day_items[day]
        canvas = self.control.canvas
        return canvas.itemcget(number, "text") + "\n" + canvas.itemcget(amount, "text")

    def click(self, day):
        canvas = self.control.canvas
        x0, y0, x1, y1 = self.control.day_bounds[day]
        x = round((x0 + x1) / 2 - canvas.canvasx(0))
        y = round((y0 + y1) / 2 - canvas.canvasy(0))
        canvas.event_generate("<Motion>", x=x, y=y)
        canvas.event_generate("<Button-1>", x=x, y=y)
        canvas.event_generate("<ButtonRelease-1>", x=x, y=y)

    def test_twelve_months_form_three_columns_and_include_leap_day(self):
        self.control.set_year(2024, {})
        self.window.update()
        self.assertEqual(set(self.control.month_items), set(range(1, 13)))
        self.assertEqual(len(self.control.day_items), 366)
        self.assertNotIn("2024-02-30", self.control.day_items)
        self.assertEqual(self.control.day_positions["2024-02-01"], (2, 0, 3))
        self.assertEqual(self.control.day_positions["2024-02-29"], (2, 4, 3))
        self.assertEqual(self.control.day_positions["2024-09-01"], (9, 0, 6))
        first, third, last = (self.control.month_bounds[m] for m in (1, 3, 12))
        self.assertGreater(third[0], first[2])
        self.assertGreater(last[1], third[3])
        self.assertAlmostEqual(last[0], third[0])

    def test_exact_daily_amounts_distinguish_recorded_zero_from_no_record(self):
        self.control.set_year(2024, {
            "2024-02-01": 33_662_720, "2024-02-02": 130_123_456, "2024-02-03": 0})
        self.window.update()
        self.assertEqual(self.day_text("2024-02-01"), "1\n33.66272")
        self.assertEqual(self.day_text("2024-02-02"), "2\n130.123456")
        self.assertEqual(self.day_text("2024-02-03"), "3\n0.00")
        self.assertEqual(self.day_text("2024-02-04"), "4\n—")
        self.assertEqual(self.control.month_totals[2], 163786176)
        total_item = self.control.month_items[2]["total"]
        self.assertEqual(self.control.canvas.itemcget(total_item, "text"), "¥ 163.786176")

    def test_clicking_canvas_date_calls_owner_once_and_highlights_date(self):
        self.control.set_year(2024, {}, selected_day="2024-02-10")
        self.window.update()
        original = self.control.day_items["2024-02-10"]
        chosen = self.control.day_items["2024-02-29"]
        self.click("2024-02-29")
        self.assertEqual(self.selected, ["2024-02-29"])
        self.control.canvas.event_generate("<Leave>")
        self.assertEqual(self.control.canvas.itemcget(chosen[0], "fill"), ACCENT)
        self.assertEqual(self.control.canvas.itemcget(chosen[1], "fill"), "white")
        self.assertNotEqual(self.control.canvas.itemcget(original[0], "fill"), ACCENT)

    def test_replacing_year_deletes_old_items_and_removes_stale_dates(self):
        self.control.set_year(2024, {"2024-02-29": 1_000_000})
        self.window.update()
        old_items = self.control.day_items["2024-02-29"]
        self.control.set_year(2025, {"2025-12-31": 0})
        self.window.update()
        self.assertEqual(len(self.control.day_items), 365)
        self.assertNotIn("2024-02-29", self.control.day_items)
        self.assertNotIn("2025-02-29", self.control.day_items)
        self.assertFalse(any(self.control.canvas.type(item) for item in old_items))
        self.control._select_day("2025-12-31")
        self.assertEqual(self.selected, ["2025-12-31"])

    def test_today_has_visible_marker_without_becoming_recorded_zero(self):
        today = date.today()
        self.control.set_year(today.year, {})
        self.window.update()
        background = self.control.day_items[today.isoformat()][0]
        self.assertEqual(self.control.canvas.itemcget(background, "outline"), ACCENT)
        self.assertEqual(self.day_text(today.isoformat()), f"{today.day}\n—")

    def test_long_amounts_have_room_and_both_scroll_directions_work(self):
        self.control.set_year(2024, {f"2024-02-{d:02d}": 130_123_456 for d in range(1, 30)})
        self.window.update()
        canvas = self.control.canvas
        x0, _, x1, _ = self.control.day_bounds["2024-02-02"]
        self.assertGreaterEqual(x1 - x0, self.control.day_font.measure("130.123456") + 4)
        text_bounds = canvas.bbox(self.control.day_items["2024-02-02"][2])
        self.assertGreaterEqual(text_bounds[0], x0)
        self.assertLessEqual(text_bounds[2], x1)
        self.assertLess(canvas.xview()[1], 1)
        self.assertLess(canvas.yview()[1], 1)
        canvas.event_generate("<MouseWheel>", delta=-120)
        canvas.event_generate("<MouseWheel>", delta=-120, state=1)
        self.window.update()
        self.assertGreater(canvas.xview()[0], 0)
        self.assertGreater(canvas.yview()[0], 0)
        canvas.xview_moveto(1)
        canvas.yview_moveto(1)
        self.window.update()
        self.click("2024-12-31")
        self.assertEqual(self.selected, ["2024-12-31"])

    def test_resize_updates_positions_without_recreating_canvas_items(self):
        self.control.set_year(2024, {})
        self.window.update()
        original_items = self.control.canvas.find_all()
        old_bounds = self.control.month_bounds[3]
        self.window.geometry("1200x640+40+40")
        self.window.update()
        self.assertEqual(self.control.canvas.find_all(), original_items)
        self.assertGreater(self.control.month_bounds[3][2], old_bounds[2])
        self.assertGreaterEqual(self.control.month_bounds[3][2], self.control.canvas.winfo_width() - 40)

    def test_switching_year_preserves_idle_boundary_and_resizes_content(self):
        self.window.update()
        for year in (2024, 2025, 2026):
            with self.subTest(year=year):
                idle_calls = []
                self.window.after_idle(lambda: idle_calls.append("idle"))
                totals = {f"2025-{m:02d}-{d:02d}": 130_123_456
                          for m in range(1, 13) for d in range(1, 29)} if year == 2025 else {}
                self.control.set_year(year, totals)
                self.assertEqual(idle_calls, [], "刷新日历应在自然空闲边界布局")
                self.window.update()
                self.assertEqual(idle_calls, ["idle"])
                self.assertTrue(all(day.startswith(str(year)) for day in self.control.day_items))
                if year == 2025:
                    self.assertLess(self.control.canvas.xview()[1], 1)
                else:
                    self.assertEqual(self.control.canvas.xview(), (0.0, 1.0))

    def test_release_then_rebuild_preserves_parent_timers_and_has_no_tcl_errors(self):
        self.control.set_year(2024, {})
        self.window.update()
        self.window.tk.eval("set ::year_calendar_background_errors {}")
        self.window.tk.eval("proc bgerror {message} {lappend ::year_calendar_background_errors $message}")
        root_calls = []
        self.window.after(50, lambda: root_calls.append("window"))
        self.click("2024-02-29")
        self.assertEqual(self.selected, ["2024-02-29"])
        self.control.set_year(2025, {})
        self.window.after(250, self.window.quit)
        self.window.mainloop()
        self.assertEqual(self.window.tk.eval("set ::year_calendar_background_errors"), "")
        self.assertEqual(root_calls, ["window"])

    def test_month_title_and_blank_cell_do_not_select_a_day(self):
        self.control.set_year(2024, {})
        self.window.update()
        canvas = self.control.canvas
        x0, y0, x1, y1 = canvas.bbox(self.control.month_items[2]["title"])
        canvas.event_generate("<ButtonRelease-1>", x=round((x0 + x1) / 2), y=round((y0 + y1) / 2))
        left, top, right, bottom = self.control.day_bounds["2024-02-01"]
        next_left = self.control.day_bounds["2024-02-02"][0]
        blank_x = round((left + right) / 2 - 3 * (next_left - left))
        canvas.event_generate("<ButtonRelease-1>", x=blank_x, y=round((top + bottom) / 2))
        self.assertEqual(self.selected, [])

    def test_mouse_event_before_idle_layout_cannot_hit_unpositioned_dates(self):
        self.control.set_year(2024, {})
        self.window.update()
        errors = []
        self.window.report_callback_exception = lambda exc, error, trace: errors.append(error)
        self.control.set_year(2025, {})
        self.control.canvas.event_generate("<Motion>", x=1, y=1)
        self.control.canvas.event_generate("<ButtonRelease-1>", x=1, y=1)
        self.assertEqual(errors, [])
        self.assertEqual(self.selected, [])
        self.window.update()
        self.assertTrue(self.control.day_bounds)


if __name__ == "__main__":
    unittest.main()
