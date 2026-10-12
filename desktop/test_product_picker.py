"""商品小计和商品选择器验收；仅使用内存中的商品快照。"""
import sqlite3
import unittest
from unittest.mock import patch

import customtkinter as ctk

from product_picker import ProductPicker, product_subtotal


def product_row(identifier=1, name="奶茶", price_units=33_662_720):
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    try:
        return connection.execute(
            "SELECT ? AS id, ? AS name, ? AS price_units",
            (identifier, name, price_units)).fetchone()
    finally:
        connection.close()


class ProductQuantityTests(unittest.TestCase):
    def test_subtotal_preserves_micro_units(self):
        self.assertEqual(product_subtotal(product_row(), "3"), (3, 100_988_160))
        self.assertEqual(product_subtotal(product_row(price_units=1), "2"), (2, 2))

    def test_zero_price_and_quantity_upper_bound_are_explicit(self):
        self.assertEqual(product_subtotal(product_row(price_units=0), "999999"), (999999, 0))
        with self.assertRaisesRegex(ValueError, "999999"):
            product_subtotal(product_row(price_units=0), "1000000")

    def test_invalid_quantities_do_not_substitute_one(self):
        for quantity in ("", "0", "-1", "1.5", "two", "２", "1000000"):
            with self.subTest(quantity=quantity):
                with self.assertRaisesRegex(ValueError, "数量"):
                    product_subtotal(product_row(), quantity)
        self.assertEqual(product_subtotal(product_row(), " 000001 "), (1, 33_662_720))

    def test_sqlite_integer_limit_is_checked_before_success(self):
        product = product_row(price_units=9_223_372_036_854_775_807)
        self.assertEqual(product_subtotal(product, "1"), (1, 9_223_372_036_854_775_807))
        with self.assertRaisesRegex(ValueError, "整数范围"):
            product_subtotal(product, "2")


class ProductPickerTests(unittest.TestCase):
    def setUp(self):
        ctk.set_appearance_mode("light")
        self.window = ctk.CTk()
        self.window.geometry("700x560+40+40")
        self.products = [product_row(), product_row(2, "零价格商品", 0)]
        self.applied = []
        self.picker = ProductPicker(
            self.window, self.products,
            lambda product, quantity, add: self.applied.append((product, quantity, add)))
        self.window.update()

    def tearDown(self):
        self.window.update_idletasks()
        widgets, owners = [self.window], {}
        while widgets:
            widget = widgets.pop()
            owners.update((command, widget) for command in widget._tclCommands or ())
            widgets.extend(widget.winfo_children())
        for callback_id in self.window.tk.call("after", "info"):
            script, _ = self.window.tk.call("after", "info", callback_id)
            owners[script.split()[0]].after_cancel(callback_id)
        self.window.destroy()

    def test_first_product_is_selected_and_preview_updates_without_rounding(self):
        self.assertEqual(self.picker.tree.selection(), ("1",))
        self.assertEqual(self.picker.quantity_var.get(), "1")
        self.assertEqual(self.picker.price_var.get(), "¥ 33.66272")
        self.picker.quantity_var.set("3")
        self.assertEqual(self.picker.subtotal_var.get(), "¥ 100.98816")
        self.picker.tree.selection_set("2")
        self.window.update()
        self.assertEqual(self.picker.price_var.get(), "¥ 0.00")
        self.assertEqual(self.picker.subtotal_var.get(), "¥ 0.00")

    def test_invalid_quantity_has_live_error_and_submit_warns_without_applying(self):
        self.picker.quantity_var.set("0")
        self.assertIn("999999", self.picker.error_var.get())
        self.assertEqual(self.picker.subtotal_var.get(), "无法计算")
        with patch("product_picker.messagebox.showwarning") as warning:
            self.picker.replace_button.invoke()
        warning.assert_called_once()
        self.assertEqual(self.applied, [])
        self.assertTrue(self.picker.winfo_exists())

    def test_replace_passes_selected_snapshot_and_quantity_then_closes(self):
        self.picker.quantity_var.set("3")
        self.picker.replace_button.invoke()
        self.assertEqual(self.applied, [(self.products[0], 3, False)])
        self.assertIs(self.applied[0][0], self.products[0])
        self.assertFalse(self.picker.winfo_exists())

    def test_add_passes_true_and_does_not_save_an_expense(self):
        self.picker.add_button.invoke()
        self.assertEqual(self.applied, [(self.products[0], 1, True)])
        self.assertFalse(self.picker.winfo_exists())

    def test_callback_input_error_warns_and_keeps_picker(self):
        def invalid_draft(product, quantity, add):
            raise ValueError("当前支出金额无效。")
        self.picker.on_apply = invalid_draft
        with patch("product_picker.messagebox.showwarning") as warning:
            self.picker.add_button.invoke()
        warning.assert_called_once()
        self.assertIn("当前支出金额无效", self.picker.error_var.get())
        self.assertTrue(self.picker.winfo_exists())

    def test_unexpected_callback_failure_reaches_tk_handler_and_keeps_picker(self):
        errors = []
        self.window.report_callback_exception = lambda exc, value, tb: errors.append(value)
        def broken_callback(product, quantity, add):
            raise RuntimeError("保存草稿失败")
        self.picker.on_apply = broken_callback
        self.picker.replace_button._text_label.event_generate("<Enter>")
        self.picker.replace_button._text_label.event_generate("<ButtonRelease-1>")
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], RuntimeError)
        self.assertTrue(self.picker.winfo_exists())

    def test_real_release_closes_without_leaving_animation_timer(self):
        self.window.tk.eval("set ::product_picker_background_errors {}")
        self.window.tk.eval(
            "proc bgerror {message} {lappend ::product_picker_background_errors $message}")
        root_calls = []
        self.window.after(50, lambda: root_calls.append("window"))
        self.picker.replace_button._text_label.event_generate("<Enter>")
        self.picker.replace_button._text_label.event_generate("<ButtonRelease-1>")
        self.window.after(250, self.window.quit)
        self.window.mainloop()
        self.assertEqual(self.window.tk.eval("set ::product_picker_background_errors"), "")
        self.assertEqual(root_calls, ["window"])
        self.assertFalse(self.picker.winfo_exists())


if __name__ == "__main__":
    unittest.main()
