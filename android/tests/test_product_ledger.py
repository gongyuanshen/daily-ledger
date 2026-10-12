"""商品管理契约：真实临时 SQLite，不接触使用中的账本。"""
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from ledger import Ledger, format_amount, parse_amount


class ProductLedgerTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="product-ledger-")
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "ledger.sqlite3"
        self.ledger = Ledger(self.path)
        self.addCleanup(self.ledger.close)

    def test_crud_normalizes_name_and_preserves_id(self):
        self.assertEqual(self.ledger.list_products(), [])
        first = self.ledger.add_product("  牛奶  ", 33_662_720)
        second = self.ledger.add_product("面包", 45_986_000)
        row = self.ledger.get_product(first)
        self.assertIsInstance(row, sqlite3.Row)
        self.assertEqual(dict(row), {"id": first, "name": "牛奶", "price_units": 33_662_720})
        self.ledger.update_product(first, "  纯牛奶  ", 1)
        self.assertEqual(dict(self.ledger.get_product(first)),
                         {"id": first, "name": "纯牛奶", "price_units": 1})
        self.ledger.delete_product(second)
        self.assertEqual([dict(row) for row in self.ledger.list_products()],
                         [{"id": first, "name": "纯牛奶", "price_units": 1}])

    def test_exact_prices_zero_and_int64_maximum_survive_reopening(self):
        prices = (0, 1, parse_amount("33.662720"), parse_amount("45.986"),
                  9_223_372_036_854_775_807)
        identifiers = [self.ledger.add_product(f"商品 {index}", price)
                       for index, price in enumerate(prices)]
        with closing(Ledger(self.path)) as reopened:
            self.assertEqual([reopened.get_product(identifier)["price_units"]
                              for identifier in identifiers],
                             [0, 1, 33_662_720, 45_986_000, 9_223_372_036_854_775_807])
            self.assertEqual(format_amount(reopened.get_product(identifiers[2])["price_units"]),
                             "33.66272")
        self.ledger.update_product(identifiers[2], "商品 2", 0)
        self.assertEqual(self.ledger.get_product(identifiers[2])["price_units"], 0)

    def test_duplicate_trimmed_name_is_rejected_without_changing_products(self):
        first = self.ledger.add_product("牛奶", 100)
        second = self.ledger.add_product("面包", 200)
        original = [dict(row) for row in self.ledger.list_products()]
        with self.assertRaises(ValueError):
            self.ledger.add_product("  牛奶  ", 300)
        with self.assertRaises(ValueError):
            self.ledger.update_product(second, " 牛奶 ", 400)
        self.assertEqual([dict(row) for row in self.ledger.list_products()], original)
        self.ledger.update_product(first, " 牛奶 ", 500)
        self.assertEqual(self.ledger.get_product(first)["price_units"], 500)

    def test_invalid_names_and_prices_are_rejected_without_changing_products(self):
        identifier = self.ledger.add_product("原商品", 100)
        original = dict(self.ledger.get_product(identifier))
        invalid = [(name, 100) for name in ("", " \t\n ", None, 123)]
        invalid.extend(("新商品", price) for price in
                       (-1, None, True, False, 1.0, 1.5, "100", 9_223_372_036_854_775_808))
        for name, price in invalid:
            with self.subTest(name=name, price=price):
                with self.assertRaises(ValueError):
                    self.ledger.add_product(name, price)
                with self.assertRaises(ValueError):
                    self.ledger.update_product(identifier, name, price)
                self.assertEqual(dict(self.ledger.get_product(identifier)), original)
                self.assertEqual(len(self.ledger.list_products()), 1)

    def test_invalid_product_input_is_rejected_before_accessing_database(self):
        self.ledger.connection.close()
        for name, price in ((" ", 0), ("正常名称", -1), ("正常名称", True),
                            ("正常名称", 1.0), ("正常名称", "1"),
                            ("正常名称", 9_223_372_036_854_775_808)):
            with self.subTest(name=name, price=price):
                with self.assertRaises(ValueError):
                    self.ledger.add_product(name, price)
                with self.assertRaises(ValueError):
                    self.ledger.update_product(1, name, price)

    def test_missing_product_read_update_delete_raise_lookup_error(self):
        identifier = self.ledger.add_product("保留商品", 100)
        for operation in (
            lambda: self.ledger.get_product(identifier + 1),
            lambda: self.ledger.update_product(identifier + 1, "不存在", 200),
            lambda: self.ledger.delete_product(identifier + 1),
        ):
            with self.assertRaises(LookupError):
                operation()
        self.assertEqual(dict(self.ledger.get_product(identifier)),
                         {"id": identifier, "name": "保留商品", "price_units": 100})
        self.ledger.delete_product(identifier)
        with self.assertRaises(LookupError):
            self.ledger.get_product(identifier)

    def test_real_readonly_write_failures_propagate_without_mutation(self):
        identifier = self.ledger.add_product("原商品", 33_662_720)
        self.ledger.close()
        self.ledger.connection = sqlite3.connect(f"{self.path.as_uri()}?mode=ro", uri=True)
        self.ledger.connection.row_factory = sqlite3.Row
        operations = (
            lambda: self.ledger.add_product("新商品", 1),
            lambda: self.ledger.update_product(identifier, "修改商品", 0),
            lambda: self.ledger.delete_product(identifier),
        )
        for operation in operations:
            with self.assertRaises(sqlite3.OperationalError) as caught:
                operation()
            self.assertEqual(caught.exception.sqlite_errorcode, sqlite3.SQLITE_READONLY)
            self.assertEqual([dict(row) for row in self.ledger.list_products()],
                             [{"id": identifier, "name": "原商品", "price_units": 33_662_720}])

    def test_product_updates_and_deletion_preserve_historical_expenses(self):
        identifier = self.ledger.add_product("牛奶", 33_662_720)
        self.ledger.add("2026-10-10", 33_662_720, "牛奶", "餐饮", "微信")
        original = [dict(row) for row in self.ledger.list_entries()]
        self.ledger.update_product(identifier, "新名称", 0)
        self.assertEqual([dict(row) for row in self.ledger.list_entries()], original)
        self.ledger.delete_product(identifier)
        self.assertEqual([dict(row) for row in self.ledger.list_entries()], original)

    def test_backup_and_restore_keep_products_prices_and_other_ledger_data(self):
        identifier = self.ledger.add_product("牛奶", 33_662_720)
        self.ledger.add("2026-10-10", 0, "零支出")
        self.ledger.set_budget("2026-10", 45_986_000)
        backup = self.path.parent / "backup.sqlite3"
        self.ledger.backup(backup)
        with closing(Ledger(backup)) as saved:
            self.assertEqual(dict(saved.get_product(identifier)),
                             {"id": identifier, "name": "牛奶", "price_units": 33_662_720})
        self.ledger.update_product(identifier, "改名", 0)
        self.ledger.add_product("后来新增", 1)
        self.ledger.restore(backup)
        self.assertEqual([dict(row) for row in self.ledger.list_products()],
                         [{"id": identifier, "name": "牛奶", "price_units": 33_662_720}])
        self.assertEqual(self.ledger.list_entries()[0]["amount_units"], 0)
        self.assertEqual(self.ledger.get_budget("2026-10"), 45_986_000)


if __name__ == "__main__":
    unittest.main()
