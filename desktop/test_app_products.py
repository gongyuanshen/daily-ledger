import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import LedgerApp
from ledger import Ledger, parse_amount


class ProductWindowTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.ledger = Ledger(Path(self.directory.name) / "ledger.sqlite3")
        self.addCleanup(self.ledger.close)
        self.window = LedgerApp(self.ledger)
        self.window.withdraw()
        self.addCleanup(self.window.destroy)

    def test_product_management_creates_edits_and_deletes_exact_prices(self):
        self.assertIn("商品管理", self.window.nav_buttons)
        self.window.show_page("商品管理")
        self.window.product_name_var.set(" 牛奶 ")
        self.window.product_price_var.set("2.876")
        self.window.save_product_button.invoke()
        row = self.ledger.list_products()[0]
        self.assertEqual((row["name"], row["price_units"]), ("牛奶", 2876000))
        self.window.product_tree.selection_set(str(row["id"]))
        self.window.edit_product()
        self.assertEqual(self.window.product_price_var.get(), "2.876")
        self.window.product_price_var.set("3.990001")
        self.window.save_product_button.invoke()
        self.assertEqual(self.ledger.get_product(row["id"])["price_units"], 3990001)
        self.window.product_tree.selection_set(str(row["id"]))
        with patch("app.messagebox.askyesno", return_value=True):
            self.window.delete_product()
        self.assertEqual(self.ledger.list_products(), [])

    def test_invalid_product_inputs_do_not_write_or_clear_draft(self):
        self.window.show_page("商品管理")
        self.window.product_name_var.set("面包")
        self.window.product_price_var.set("3.1234567")
        with patch("app.messagebox.showwarning") as warning:
            self.window.save_product_button.invoke()
        warning.assert_called_once()
        self.assertEqual(self.ledger.list_products(), [])
        self.assertEqual(self.window.product_name_var.get(), "面包")
        self.window.product_price_var.set("3")
        self.window.save_product_button.invoke()
        self.window.product_name_var.set("面包")
        self.window.product_price_var.set("4")
        with patch("app.messagebox.showwarning") as warning:
            self.window.save_product_button.invoke()
        warning.assert_called_once()
        self.assertEqual(len(self.ledger.list_products()), 1)

    def test_selected_products_fill_and_accumulate_without_saving_until_requested(self):
        first = self.ledger.add_product("牛奶", parse_amount("2.876"))
        second = self.ledger.add_product("面包", parse_amount("3.99"))
        self.window.apply_product(self.ledger.get_product(first), 2, False)
        self.assertEqual(self.window.amount_var.get(), "5.752")
        self.assertIn("牛奶", self.window.note_var.get())
        self.window.apply_product(self.ledger.get_product(second), 1, True)
        self.assertEqual(self.window.amount_var.get(), "9.742")
        self.assertIn("面包", self.window.note_var.get())
        self.assertEqual(self.ledger.list_entries(), [])
        self.window.amount_var.set("10.25")
        self.window.save_button.invoke()
        row = self.ledger.list_entries()[0]
        self.assertEqual(row["amount_units"], 10250000)
        self.ledger.update_product(first, "牛奶新版", parse_amount("20"))
        self.ledger.delete_product(second)
        self.assertEqual(self.ledger.list_entries()[0]["amount_units"], 10250000)

    def test_invalid_existing_amount_and_overflow_leave_form_unchanged(self):
        product_id = self.ledger.add_product("公交", parse_amount("2"))
        row = self.ledger.get_product(product_id)
        for draft in ("bad", "9223372036854.775807"):
            self.window.amount_var.set(draft)
            self.window.note_var.set("自己的备注")
            with self.assertRaises(ValueError):
                self.window.apply_product(row, 1, True)
            self.assertEqual(self.window.amount_var.get(), draft)
            self.assertEqual(self.window.note_var.get(), "自己的备注")

    def test_replacing_amount_preserves_custom_note_and_other_expense_fields(self):
        product_id = self.ledger.add_product("早餐", parse_amount("5"))
        self.window.amount_var.set("待重新计算")
        self.window.note_var.set("和同事一起")
        self.window.entry_day_var.set("2024-09-05")
        self.window.category_var.set("餐饮")
        self.window.payment_var.set("微信")
        self.window.apply_product(self.ledger.get_product(product_id), 3, False)
        self.assertEqual(self.window.amount_var.get(), "15.00")
        self.assertEqual(self.window.note_var.get(), "和同事一起")
        self.assertEqual(self.window.entry_day_var.get(), "2024-09-05")
        self.assertEqual(self.window.category_var.get(), "餐饮")
        self.assertEqual(self.window.payment_var.get(), "微信")

    def test_replacing_product_replaces_its_generated_note(self):
        first = self.ledger.add_product("牛奶", parse_amount("2.876"))
        second = self.ledger.add_product("面包", parse_amount("3.99"))
        self.window.apply_product(self.ledger.get_product(first), 2, False)
        self.window.apply_product(self.ledger.get_product(second), 1, False)
        self.assertEqual(self.window.amount_var.get(), "3.99")
        self.assertEqual(self.window.note_var.get(), "面包 × 1")

    def test_empty_catalog_opens_product_management_without_fake_selection(self):
        self.assertIsNone(self.window.open_product_picker())
        self.assertEqual(self.window.page_title_var.get(), "商品管理")
        self.assertEqual(self.window.amount_var.get(), "")
        self.assertEqual(self.ledger.list_entries(), [])

    def test_restore_refreshes_catalog_and_discards_stale_product_edit(self):
        old_id = self.ledger.add_product("旧商品", parse_amount("1"))
        backup_path = Path(self.directory.name) / "source.sqlite3"
        source = Ledger(backup_path)
        source.add_product("新商品", parse_amount("8.866"))
        source.close()
        self.window.show_page("商品管理")
        self.window.product_tree.selection_set(str(old_id))
        self.window.edit_product()
        self.assertEqual(self.window.product_editing_id, old_id)
        with patch("app.filedialog.askopenfilename", return_value=str(backup_path)), \
                patch("app.messagebox.askyesno", return_value=True):
            self.window.restore_ledger()
        self.assertIsNone(self.window.product_editing_id)
        self.assertEqual(self.window.product_name_var.get(), "")
        self.window.show_page("商品管理")
        names = [self.window.product_tree.item(item, "values")[0]
                 for item in self.window.product_tree.get_children()]
        self.assertEqual(names, ["新商品"])


if __name__ == "__main__":
    unittest.main()
