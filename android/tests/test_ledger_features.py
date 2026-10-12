import csv
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from ledger import Ledger


def create_legacy(path, amount_cents=123456):
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day TEXT NOT NULL,
                amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
                note TEXT NOT NULL
            ) STRICT
        """)
        connection.execute("CREATE INDEX IF NOT EXISTS expenses_day ON expenses(day)")
        connection.execute(
            "INSERT INTO expenses (id, day, amount_cents, note) VALUES (?, ?, ?, ?)",
            (7, "2026-10-09", amount_cents, "历史中文 ' ?"),
        )
        connection.commit()


def create_v1(path, amount_cents=123456, budget_cents=50000):
    create_legacy(path, amount_cents)
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("ALTER TABLE expenses ADD COLUMN category TEXT NOT NULL DEFAULT '未分类'")
        connection.execute("ALTER TABLE expenses ADD COLUMN payment TEXT NOT NULL DEFAULT '未指定'")
        connection.execute("UPDATE expenses SET category = '自定义', payment = '微信'")
        connection.execute("""
            CREATE TABLE budgets (
                month TEXT PRIMARY KEY,
                amount_cents INTEGER NOT NULL CHECK (amount_cents > 0)
            ) STRICT
        """)
        connection.execute("INSERT INTO budgets VALUES ('2026-10', ?)", (budget_cents,))
        connection.execute("PRAGMA user_version = 1")
        connection.commit()


def create_v2(path):
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("""
            CREATE TABLE expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day TEXT NOT NULL,
                amount_units INTEGER NOT NULL CHECK (amount_units >= 0),
                note TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT '未分类',
                payment TEXT NOT NULL DEFAULT '未指定'
            ) STRICT
        """)
        connection.execute("CREATE INDEX expenses_day ON expenses(day)")
        connection.execute("""
            CREATE TABLE budgets (
                month TEXT PRIMARY KEY,
                amount_units INTEGER NOT NULL CHECK (amount_units > 0)
            ) STRICT
        """)
        connection.execute("INSERT INTO expenses VALUES (7, '2026-10-09', 33662720, '六位原文', '餐饮', '微信')")
        connection.execute("INSERT INTO expenses VALUES (20, '2026-10-10', 0, '', '未分类', '未指定')")
        connection.execute("DELETE FROM expenses WHERE id = 20")
        connection.execute("INSERT INTO budgets VALUES ('2026-10', 500000000)")
        connection.execute("PRAGMA user_version = 2")
        connection.commit()


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="ledger-features-")
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "账本.sqlite3"

    def open_ledger(self):
        ledger = Ledger(self.path)
        self.addCleanup(ledger.close)
        return ledger

    def test_new_database_has_current_strict_schema_without_migration_backup(self):
        ledger = self.open_ledger()
        self.assertEqual(ledger.connection.execute("PRAGMA user_version").fetchone()[0], 3)
        columns = ledger.connection.execute("PRAGMA table_info(expenses)").fetchall()
        self.assertEqual([row[1] for row in columns],
                         ["id", "day", "amount_units", "note", "category", "payment"])
        self.assertEqual(ledger.connection.execute("SELECT COUNT(*) FROM budgets").fetchone()[0], 0)
        self.assertEqual(ledger.connection.execute("SELECT COUNT(*) FROM products").fetchone()[0], 0)
        self.assertFalse((self.path.parent / "backups").exists())

    def test_legacy_migration_preserves_every_original_field_and_keeps_original_backup(self):
        create_legacy(self.path)
        ledger = self.open_ledger()
        row = ledger.connection.execute("SELECT * FROM expenses").fetchone()
        self.assertEqual(tuple(row), (7, "2026-10-09", 1234560000,
                                     "历史中文 ' ?", "未分类", "未指定"))
        backups = list((self.path.parent / "backups").glob("*.sqlite3"))
        self.assertEqual(len(backups), 1)
        with closing(sqlite3.connect(backups[0])) as saved:
            self.assertEqual(saved.execute("PRAGMA user_version").fetchone()[0], 0)
            self.assertEqual(saved.execute("SELECT * FROM expenses").fetchall(),
                             [(7, "2026-10-09", 123456, "历史中文 ' ?")])
        ledger.close()
        reopened = self.open_ledger()
        self.assertEqual(reopened.connection.execute("PRAGMA user_version").fetchone()[0], 3)
        self.assertEqual(len(list((self.path.parent / "backups").glob("*.sqlite3"))), 1)

    def test_unknown_newer_version_is_rejected_without_changing_the_database(self):
        create_legacy(self.path)
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute("PRAGMA user_version = 9")
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            self.open_ledger()
        self.assertEqual(self.path.read_bytes(), before)
        self.assertFalse((self.path.parent / "backups").exists())

    def test_unrelated_sqlite_database_is_rejected_without_creating_ledger_tables(self):
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute("CREATE TABLE another_app (id INTEGER)")
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            self.open_ledger()
        self.assertEqual(self.path.read_bytes(), before)

    def test_unknown_unique_index_is_rejected_before_migration(self):
        create_legacy(self.path)
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute("CREATE UNIQUE INDEX only_one_expense_per_day ON expenses(day)")
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            self.open_ledger()
        self.assertEqual(self.path.read_bytes(), before)

    def test_changed_day_index_is_rejected_instead_of_breaking_same_day_entries(self):
        create_legacy(self.path)
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute("DROP INDEX expenses_day")
            connection.execute("CREATE UNIQUE INDEX expenses_day ON expenses(day)")
        with self.assertRaises(ValueError):
            self.open_ledger()

    def test_similarly_named_external_tables_are_not_treated_as_sqlite_internal_tables(self):
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute("CREATE TABLE sqlitex_other_app (id INTEGER)")
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            self.open_ledger()
        self.assertEqual(self.path.read_bytes(), before)

    def test_database_failure_after_first_schema_changes_rolls_back_entire_migration(self):
        create_legacy(self.path)
        original_bytes = self.path.read_bytes()
        native_connect = sqlite3.connect
        failing_connection = native_connect(self.path)
        failing_connection.set_authorizer(
            lambda operation, name, *_: sqlite3.SQLITE_DENY
            if operation == sqlite3.SQLITE_CREATE_TABLE and name == "budgets" else sqlite3.SQLITE_OK
        )

        def connect(path, *arguments, **keywords):
            if Path(path).resolve() == self.path:
                return failing_connection
            return native_connect(path, *arguments, **keywords)

        with patch("ledger.sqlite3.connect", side_effect=connect), self.assertRaises(sqlite3.DatabaseError):
            self.open_ledger()
        self.assertEqual(self.path.read_bytes(), original_bytes)
        with closing(native_connect(self.path)) as observer:
            self.assertEqual([row[1] for row in observer.execute("PRAGMA table_info(expenses)")],
                             ["id", "day", "amount_cents", "note"])
            self.assertEqual(observer.execute("PRAGMA user_version").fetchone()[0], 0)
        self.assertEqual(len(list((self.path.parent / "backups").glob("*.sqlite3"))), 1)

    def test_migration_backup_failure_does_not_modify_original_database(self):
        create_legacy(self.path)
        original_bytes = self.path.read_bytes()
        (self.path.parent / "backups").write_text("blocking directory creation", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            self.open_ledger()
        self.assertEqual(self.path.read_bytes(), original_bytes)

    def test_extra_column_check_is_rejected_as_an_unknown_business_constraint(self):
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute("""
                CREATE TABLE expenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    day TEXT NOT NULL,
                    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
                    note TEXT NOT NULL CHECK (note != '禁止备注')
                ) STRICT
            """)
        original_bytes = self.path.read_bytes()
        with self.assertRaises(ValueError):
            self.open_ledger()
        self.assertEqual(self.path.read_bytes(), original_bytes)

    def test_budget_extra_unique_constraint_is_rejected(self):
        ledger = self.open_ledger()
        ledger.close()
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute("DROP TABLE budgets")
            connection.execute("""
                CREATE TABLE budgets (
                    month TEXT PRIMARY KEY,
                    amount_units INTEGER NOT NULL CHECK (amount_units > 0) UNIQUE
                ) STRICT
            """)
        original_bytes = self.path.read_bytes()
        with self.assertRaises(ValueError):
            self.open_ledger()
        self.assertEqual(self.path.read_bytes(), original_bytes)

    def test_v1_migration_scales_expenses_and_budget_and_preserves_metadata_and_sequence(self):
        create_v1(self.path)
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute("INSERT INTO expenses (id, day, amount_cents, note) VALUES (20, '2026-10-10', 1, '')")
            connection.execute("DELETE FROM expenses WHERE id = 20")
            connection.commit()
        ledger = self.open_ledger()
        self.assertEqual(tuple(ledger.list_entries()[0]),
                         (7, "2026-10-09", 1234560000, "历史中文 ' ?", "自定义", "微信"))
        self.assertEqual(ledger.get_budget("2026-10"), 500000000)
        self.assertEqual(ledger.add("2026-10-10", 0, "明确零金额"), 21)
        saved = list((self.path.parent / "backups").glob("*-before-v3-*.sqlite3"))
        self.assertEqual(len(saved), 1)
        with closing(sqlite3.connect(saved[0])) as backup:
            self.assertEqual(backup.execute("PRAGMA user_version").fetchone()[0], 1)
            self.assertEqual(backup.execute("SELECT amount_cents FROM budgets").fetchone()[0], 50000)

    def test_legacy_integer_conversion_overflow_rejects_without_modifying_source(self):
        for version, expense, budget in ((0, 9223372036854775807, 1),
                                         (1, 922337203685477, 922337203685478)):
            with self.subTest(version=version):
                source = self.path.parent / f"overflow-v{version}.sqlite3"
                if version == 0:
                    create_legacy(source, expense)
                else:
                    create_v1(source, expense, budget)
                original_bytes = source.read_bytes()
                with self.assertRaises(ValueError), closing(Ledger(source)):
                    pass
                self.assertEqual(source.read_bytes(), original_bytes)

    def test_largest_convertible_legacy_cent_amount_remains_an_exact_integer(self):
        create_legacy(self.path, 922337203685477)
        ledger = self.open_ledger()
        self.assertEqual(ledger.list_entries()[0]["amount_units"], 9223372036854770000)

    def test_empty_legacy_table_keeps_deleted_record_autoincrement_history(self):
        create_legacy(self.path)
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute("DELETE FROM expenses")
            connection.commit()
        ledger = self.open_ledger()
        self.assertEqual(ledger.list_entries(), [])
        self.assertEqual(ledger.add("2026-10-10", 0, "明确零金额"), 8)

    def test_v2_migration_only_adds_products_and_preserves_expenses_budget_and_sequence(self):
        create_v2(self.path)
        ledger = self.open_ledger()
        self.assertEqual(ledger.connection.execute("PRAGMA user_version").fetchone()[0], 3)
        self.assertEqual(tuple(ledger.list_entries()[0]),
                         (7, "2026-10-09", 33662720, "六位原文", "餐饮", "微信"))
        self.assertEqual(ledger.get_budget("2026-10"), 500000000)
        self.assertEqual(ledger.list_products(), [])
        self.assertEqual(ledger.add("2026-10-10", 0, "明确零金额"), 21)
        backups = list((self.path.parent / "backups").glob("*-before-v3-*.sqlite3"))
        self.assertEqual(len(backups), 1)
        with closing(sqlite3.connect(backups[0])) as saved:
            self.assertEqual(saved.execute("PRAGMA user_version").fetchone()[0], 2)
            self.assertIsNone(saved.execute("SELECT name FROM sqlite_master WHERE name = 'products'").fetchone())
            self.assertEqual(saved.execute("SELECT seq FROM sqlite_sequence WHERE name = 'expenses'").fetchone()[0], 20)

    def test_product_table_failure_rolls_back_every_upgrade_and_preserves_backup(self):
        native_connect = sqlite3.connect
        for version, create in ((0, create_legacy), (1, create_v1), (2, create_v2)):
            with self.subTest(version=version):
                source = self.path.parent / f"product-failure-v{version}.sqlite3"
                create(source)
                original_bytes = source.read_bytes()
                denied_connection = native_connect(source)
                denied_connection.set_authorizer(
                    lambda operation, name, *_: sqlite3.SQLITE_DENY
                    if operation == sqlite3.SQLITE_CREATE_TABLE and name == "products" else sqlite3.SQLITE_OK
                )

                def connect(path, *arguments, **keywords):
                    return denied_connection if Path(path).resolve() == source else native_connect(path, *arguments, **keywords)

                with patch("ledger.sqlite3.connect", side_effect=connect), self.assertRaises(sqlite3.DatabaseError), closing(Ledger(source)):
                    pass
                self.assertEqual(source.read_bytes(), original_bytes)
                self.assertEqual(len(list((source.parent / "backups").glob(f"{source.stem}-before-v3-*.sqlite3"))), 1)


class TemporaryLedgerCase(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="ledger-entries-")
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "账本.sqlite3"
        self.ledger = Ledger(self.path)
        self.addCleanup(self.ledger.close)


class EntryFeatureTests(TemporaryLedgerCase):
    def test_zero_records_count_and_keep_day_but_do_not_create_zero_category_share(self):
        self.ledger.add("2026-10-10", 0, "原文零金额", "零金额汇总", "未指定")
        self.ledger.add("2026-10-11", 33662720, "六位原文", "餐饮", "现金")
        self.assertEqual(self.ledger.month_summary("2026-10"), {
            "total_units": 33662720, "count": 2,
            "by_category": [("餐饮", 33662720)],
            "by_day": {"2026-10-10": 0, "2026-10-11": 33662720},
        })
    def test_existing_add_and_list_day_keep_compatibility_with_explicit_unknown_labels(self):
        self.ledger.add("2026-10-10", 100, "早餐")
        self.assertEqual(tuple(self.ledger.list_day("2026-10-10")[0]),
                         (1, "2026-10-10", 100, "早餐"))
        self.assertTrue(hasattr(self.ledger, "list_entries"), "缺少六列明细查询")
        self.assertEqual(dict(self.ledger.list_entries()[0]), {
            "id": 1, "day": "2026-10-10", "amount_units": 100,
            "note": "早餐", "category": "未分类", "payment": "未指定",
        })

    def test_edit_without_metadata_keeps_existing_category_and_payment(self):
        record_id = self.ledger.add("2026-10-10", 1250, "早餐", "餐饮", "微信")
        self.ledger.update(record_id, "2026-10-11", 1500, "午餐")
        self.assertEqual(tuple(self.ledger.list_entries()[0]),
                         (record_id, "2026-10-11", 1500, "午餐", "餐饮", "微信"))
        self.ledger.update(record_id, "2026-10-11", 1600, "车费", "交通", "现金")
        self.assertEqual(tuple(self.ledger.list_entries()[0])[-2:], ("交通", "现金"))

    def test_entry_filters_are_inclusive_intersected_and_literal(self):
        first = self.ledger.add("2026-10-09", 100, "折扣 20%", "餐饮", "微信")
        second = self.ledger.add("2026-10-10", 200, "折扣 20_", "餐饮", "微信")
        self.ledger.add("2026-10-11", 300, "普通备注", "交通", "现金")
        fourth = self.ledger.add("2026-10-10", 400, "普通备注", "餐饮", "现金")
        self.assertEqual([row["id"] for row in self.ledger.list_entries()], [3, fourth, second, first])
        self.assertEqual([row["id"] for row in self.ledger.list_entries(
            "2026-10-09", "2026-10-10", "餐饮", "微信", "%")], [first])
        self.assertEqual([row["id"] for row in self.ledger.list_entries(keyword="_")], [second])
        self.assertEqual([row["id"] for row in self.ledger.list_entries(keyword="现金")], [3, fourth])
        self.assertEqual([row["id"] for row in self.ledger.list_entries(keyword="交通")], [3])
        self.assertEqual(self.ledger.list_entries(keyword="' OR 1=1 --"), [])

    def test_invalid_filter_dates_and_reversed_range_are_rejected(self):
        self.assertTrue(hasattr(self.ledger, "list_entries"), "缺少筛选入口")
        for arguments in ({"start_day": "2026-02-29"}, {"end_day": "bad"},
                          {"start_day": "2026-10-11", "end_day": "2026-10-10"}):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                self.ledger.list_entries(**arguments)

    def test_options_include_base_choices_and_distinct_existing_custom_values(self):
        self.ledger.add("2026-10-10", 100, "", "宠物", "信用卡")
        self.ledger.add("2026-10-11", 100, "", "宠物", "信用卡")
        self.assertEqual(self.ledger.categories(),
                         ["未分类", "餐饮", "交通", "购物", "居住", "娱乐", "医疗", "教育", "通讯", "其他", "宠物"])
        self.assertEqual(self.ledger.payments(),
                         ["未指定", "微信", "支付宝", "银行卡", "现金", "其他", "信用卡"])

    def test_month_summary_uses_exact_python_integer_totals_and_excludes_other_months(self):
        self.ledger.add("2026-10-01", 9223372036854775807, "", "购物", "现金")
        self.ledger.add("2026-10-01", 9223372036854775807, "", "购物", "现金")
        self.ledger.add("2026-10-31", 30, "", "餐饮", "微信")
        self.ledger.add("2026-11-01", 500, "", "餐饮", "微信")
        self.assertEqual(self.ledger.month_summary("2026-10"), {
            "total_units": 18446744073709551644, "count": 3,
            "by_category": [("购物", 18446744073709551614), ("餐饮", 30)],
            "by_day": {"2026-10-01": 18446744073709551614, "2026-10-31": 30},
        })
        self.assertEqual(self.ledger.month_summary("2024-02"), {
            "total_units": 0, "count": 0, "by_category": [], "by_day": {},
        })
        with self.assertRaises(ValueError):
            self.ledger.month_summary("2026-13")

    def test_budget_is_unset_until_explicitly_saved_and_survives_reopening(self):
        self.assertTrue(hasattr(self.ledger, "get_budget"), "缺少月预算")
        self.assertIsNone(self.ledger.get_budget("2026-10"))
        self.ledger.set_budget("2026-10", 10000)
        self.ledger.set_budget("2026-10", 15000)
        with closing(Ledger(self.path)) as observer:
            self.assertEqual(observer.get_budget("2026-10"), 15000)
            self.assertIsNone(observer.get_budget("2026-11"))
        self.ledger.clear_budget("2026-10")
        self.assertIsNone(self.ledger.get_budget("2026-10"))

    def test_budget_rejects_invalid_months_and_invalid_amounts_without_discarding_previous_value(self):
        self.assertTrue(hasattr(self.ledger, "set_budget"), "缺少月预算")
        self.ledger.set_budget("2026-10", 300)
        for amount in (0, -1, None, 1.5):
            with self.subTest(amount=amount), self.assertRaises(sqlite3.IntegrityError):
                self.ledger.set_budget("2026-10", amount)
            self.assertEqual(self.ledger.get_budget("2026-10"), 300)
        for month in ("2026-00", "2026-13", "2026-1", "202610", "not-a-month"):
            with self.subTest(month=month), self.assertRaises(ValueError):
                self.ledger.set_budget(month, 100)


class YearSummaryTests(TemporaryLedgerCase):
    def test_year_summary_isolates_year_and_accumulates_same_day_exact_micro_units(self):
        self.ledger.add("2025-12-31", 5000000, "上一年")
        self.ledger.add("2026-01-01", 33662720, "第一笔")
        self.ledger.add("2026-01-01", 45986000, "第二笔")
        self.ledger.add("2026-12-31", 0, "明确零金额")
        self.ledger.add("2027-01-01", 7000000, "下一年")
        self.assertTrue(hasattr(self.ledger, "year_summary"), "缺少年度汇总")
        queries = []
        self.ledger.connection.set_trace_callback(queries.append)
        self.assertEqual(self.ledger.year_summary(2026), {
            "total_units": 79648720, "count": 3,
            "by_day": {"2026-01-01": 79648720, "2026-12-31": 0},
        })
        self.assertEqual(len([query for query in queries if query.lstrip().upper().startswith("SELECT")]), 1)

    def test_year_summary_keeps_leap_day_and_uses_python_integer_totals(self):
        self.ledger.add("2023-02-28", 1000000, "上一年")
        self.ledger.add("2024-02-29", 9223372036854775807, "闰日")
        self.ledger.add("2024-02-29", 1, "最小微元")
        self.assertTrue(hasattr(self.ledger, "year_summary"), "缺少年度汇总")
        self.assertEqual(self.ledger.year_summary(2024), {
            "total_units": 9223372036854775808, "count": 2,
            "by_day": {"2024-02-29": 9223372036854775808},
        })
        for year in (1, 2022, 9999):
            with self.subTest(year=year):
                self.assertEqual(self.ledger.year_summary(year), {
                    "total_units": 0, "count": 0, "by_day": {},
                })

    def test_invalid_years_are_rejected_before_accessing_database(self):
        self.assertTrue(hasattr(self.ledger, "year_summary"), "缺少年度汇总入口")
        self.ledger.connection.set_authorizer(
            lambda operation, *_: sqlite3.SQLITE_DENY
            if operation == sqlite3.SQLITE_SELECT else sqlite3.SQLITE_OK
        )
        for year in (0, -1, 10000, True, False, "2026", 2026.0, None):
            with self.subTest(year=year), self.assertRaises(ValueError):
                self.ledger.year_summary(year)


class BackupRestoreTests(TemporaryLedgerCase):
    def test_restore_rejects_product_name_with_uncleaned_whitespace_and_preserves_current_database(self):
        self.ledger.add("2026-10-10", 33662720, "当前记录")
        self.ledger.add_product("当前商品", 45986000)
        original_bytes = self.path.read_bytes()
        source = self.path.parent / "未规范商品备份.sqlite3"
        with closing(Ledger(source)) as saved:
            saved.connection.execute("INSERT INTO products (name, price_units) VALUES (?, ?)", ("\t商品", 1))
            saved.connection.commit()
        with self.assertRaises(ValueError):
            self.ledger.restore(source)
        self.assertEqual(self.path.read_bytes(), original_bytes)
        self.assertEqual(self.ledger.list_products()[0]["name"], "当前商品")

    def test_restore_v2_backup_upgrades_schema_without_changing_values_or_source(self):
        source = self.path.parent / "v2备份.sqlite3"
        create_v2(source)
        original_bytes = source.read_bytes()
        self.ledger.restore(source)
        self.assertEqual(self.ledger.connection.execute("PRAGMA user_version").fetchone()[0], 3)
        self.assertEqual(self.ledger.list_entries()[0]["amount_units"], 33662720)
        self.assertEqual(self.ledger.get_budget("2026-10"), 500000000)
        self.assertEqual(self.ledger.list_products(), [])
        self.assertEqual(source.read_bytes(), original_bytes)

    def test_csv_keeps_up_to_six_fractional_digits_without_rounding(self):
        self.ledger.add("2026-10-09", 33662720, "")
        self.ledger.add("2026-10-10", 45986000, "")
        self.ledger.add("2026-10-11", 1, "")
        self.ledger.add("2026-10-12", 0, "")
        destination = self.path.parent / "原文精度.csv"
        self.ledger.export_csv(destination, self.ledger.list_entries())
        with destination.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.reader(stream))[1:]
        self.assertEqual([row[1] for row in rows], ["0.00", "0.000001", "45.986", "33.66272"])

    def test_restore_v1_backup_scales_budget_and_keeps_source_bytes(self):
        source = self.path.parent / "v1备份.sqlite3"
        create_v1(source)
        original_bytes = source.read_bytes()
        self.ledger.restore(source)
        self.assertEqual(self.ledger.list_entries()[0]["amount_units"], 1234560000)
        self.assertEqual(self.ledger.get_budget("2026-10"), 500000000)
        self.assertEqual(source.read_bytes(), original_bytes)

    def test_restore_overflowing_legacy_backup_preserves_current_data(self):
        self.ledger.add("2026-10-10", 33662720, "当前记录")
        self.ledger.set_budget("2026-10", 100000000)
        original_bytes = self.path.read_bytes()
        source = self.path.parent / "不能缩放的旧备份.sqlite3"
        create_legacy(source, 9223372036854775807)
        with self.assertRaises(ValueError):
            self.ledger.restore(source)
        self.assertEqual(self.path.read_bytes(), original_bytes)
        self.assertEqual(self.ledger.list_entries()[0]["amount_units"], 33662720)
        self.assertEqual(self.ledger.get_budget("2026-10"), 100000000)

    def test_csv_rejects_current_database_path_before_opening_output(self):
        self.ledger.add("2026-10-10", 100, "保留")
        original_bytes = self.path.read_bytes()
        with self.assertRaises(ValueError):
            self.ledger.export_csv(self.path, self.ledger.list_entries())
        self.assertEqual(self.path.read_bytes(), original_bytes)
        with closing(Ledger(self.path)) as observer:
            self.assertEqual(observer.list_entries()[0]["note"], "保留")

    def test_csv_rejects_hardlink_to_current_database(self):
        self.ledger.add("2026-10-10", 100, "保留")
        alias = self.path.parent / "账本别名.sqlite3"
        os.link(self.path, alias)
        original_bytes = self.path.read_bytes()
        with self.assertRaises(ValueError):
            self.ledger.export_csv(alias, self.ledger.list_entries())
        self.assertEqual(self.path.read_bytes(), original_bytes)

    def test_backup_and_restore_reject_hardlink_to_current_database(self):
        alias = self.path.parent / "账本别名.sqlite3"
        os.link(self.path, alias)
        original_bytes = self.path.read_bytes()
        with self.assertRaises(ValueError):
            self.ledger.backup(alias)
        with self.assertRaises(ValueError):
            self.ledger.restore(alias)
        self.assertEqual(self.path.read_bytes(), original_bytes)

    def test_csv_preserves_exact_cents_unicode_and_csv_structure(self):
        self.ledger.add("2026-10-10", 9223372036854775807, '中文,引号"\n下一行', "餐饮", "微信")
        destination = self.path.parent / "导出.csv"
        self.assertTrue(hasattr(self.ledger, "export_csv"), "缺少 CSV 导出")
        self.ledger.export_csv(destination, self.ledger.list_entries())
        self.assertTrue(destination.read_bytes().startswith(b"\xef\xbb\xbf"))
        with destination.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.reader(stream))
        self.assertEqual(rows, [
            ["日期", "金额", "分类", "支付方式", "备注"],
            ["2026-10-10", "9223372036854.775807", "餐饮", "微信", '中文,引号"\n下一行'],
        ])

    def test_csv_neutralizes_formula_prefixes_without_changing_database_text(self):
        self.assertTrue(hasattr(self.ledger, "export_csv"), "缺少 CSV 导出")
        notes = ("=1+1", "+SUM(A1)", "-2+1", "@SUM(A1)", "\t=1+1", "\r=1+1", "  =1+1", "普通备注")
        for note in notes:
            self.ledger.add("2026-10-10", 1, note, "=分类", "+支付")
        destination = self.path.parent / "安全导出.csv"
        entries = self.ledger.list_entries()
        self.ledger.export_csv(destination, entries)
        with destination.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.reader(stream))[1:]
        self.assertEqual([row[4] for row in rows],
                         ["普通备注", "'  =1+1", "'\r=1+1", "'\t=1+1", "'@SUM(A1)", "'-2+1", "'+SUM(A1)", "'=1+1"])
        self.assertTrue(all(row[2:4] == ["'=分类", "'+支付"] for row in rows))
        self.assertEqual([row["note"] for row in self.ledger.list_entries()], list(reversed(notes)))

    def test_backup_captures_committed_wal_records_budget_and_autoincrement_state(self):
        self.ledger.connection.execute("PRAGMA journal_mode = WAL")
        kept = self.ledger.add("2026-10-10", 1234, "原记录", "餐饮", "微信")
        deleted = self.ledger.add("2026-10-10", 200, "已删除")
        self.ledger.delete(deleted)
        self.ledger.set_budget("2026-10", 30000)
        destination = self.path.parent / "完整备份.sqlite3"
        self.ledger.backup(destination)
        with closing(Ledger(destination)) as saved:
            self.assertEqual(tuple(saved.list_entries()[0]), (kept, "2026-10-10", 1234, "原记录", "餐饮", "微信"))
            self.assertEqual(saved.get_budget("2026-10"), 30000)
            self.assertGreater(saved.add("2026-10-11", 1, "新记录"), deleted)
        with self.assertRaises(ValueError):
            self.ledger.backup(self.path)

    def test_restore_replaces_whole_database_and_keeps_connection_usable(self):
        self.assertTrue(hasattr(self.ledger, "restore"), "缺少安全恢复")
        self.ledger.add("2026-10-10", 100, "已备份", "交通", "现金")
        self.ledger.set_budget("2026-10", 5000)
        saved = self.path.parent / "待恢复.sqlite3"
        self.ledger.backup(saved)
        self.ledger.add("2026-10-11", 300, "之后新增")
        self.ledger.set_budget("2026-10", 9999)
        self.ledger.restore(saved)
        self.assertEqual([tuple(row) for row in self.ledger.list_entries()],
                         [(1, "2026-10-10", 100, "已备份", "交通", "现金")])
        self.assertEqual(self.ledger.get_budget("2026-10"), 5000)
        self.assertEqual(self.ledger.add("2026-10-12", 400, "恢复后新记录"), 2)
        with closing(Ledger(self.path)) as observer:
            self.assertEqual(len(observer.list_entries()), 2)

    def test_restore_accepts_legacy_backup_without_modifying_source(self):
        self.assertTrue(hasattr(self.ledger, "restore"), "缺少旧版恢复")
        source = self.path.parent / "旧版.sqlite3"
        create_legacy(source)
        original_bytes = source.read_bytes()
        self.ledger.add("2026-10-10", 100, "被替换")
        self.ledger.restore(source)
        self.assertEqual(tuple(self.ledger.list_entries()[0]),
                         (7, "2026-10-09", 1234560000, "历史中文 ' ?", "未分类", "未指定"))
        self.assertEqual(source.read_bytes(), original_bytes)
        self.assertIsNone(self.ledger.get_budget("2026-10"))
        self.assertFalse((source.parent / "backups").exists())

    def test_invalid_restore_sources_never_change_current_data(self):
        self.assertTrue(hasattr(self.ledger, "restore"), "缺少安全恢复")
        self.ledger.add("2026-10-10", 1234, "必须保留", "餐饮", "微信")
        self.ledger.set_budget("2026-10", 6789)
        sources = []
        for name in ("random", "future", "invalid-date", "trigger", "unique-index", "empty"):
            source = self.path.parent / f"{name}.sqlite3"
            with closing(sqlite3.connect(source)) as connection:
                if name == "random":
                    connection.execute("CREATE TABLE other (id INTEGER)")
            if name in ("future", "invalid-date", "trigger", "unique-index"):
                create_legacy(source)
                with closing(sqlite3.connect(source)) as connection:
                    if name == "future":
                        connection.execute("PRAGMA user_version = 7")
                    elif name == "invalid-date":
                        connection.execute("UPDATE expenses SET day = '2026-02-30'")
                    elif name == "trigger":
                        connection.execute("CREATE TRIGGER unknown_trigger AFTER INSERT ON expenses BEGIN DELETE FROM expenses; END")
                    else:
                        connection.execute("CREATE UNIQUE INDEX only_one_expense_per_day ON expenses(day)")
                    connection.commit()
            sources.append(source)
        corrupt = self.path.parent / "损坏.sqlite3"
        corrupt.write_bytes(b"not a sqlite database")
        sources.extend((corrupt, self.path.parent / "不存在.sqlite3", self.path))
        original_bytes = self.path.read_bytes()
        for source in sources:
            with self.subTest(source=source.name), self.assertRaises((ValueError, sqlite3.DatabaseError)):
                self.ledger.restore(source)
            self.assertEqual(self.path.read_bytes(), original_bytes)
            self.assertEqual([tuple(row) for row in self.ledger.list_entries()],
                             [(1, "2026-10-10", 1234, "必须保留", "餐饮", "微信")])
            self.assertEqual(self.ledger.get_budget("2026-10"), 6789)

    def test_restore_destination_write_error_propagates_and_preserves_current_records(self):
        self.assertTrue(hasattr(self.ledger, "restore"), "缺少安全恢复")
        self.ledger.add("2026-10-10", 100, "备份内容")
        source = self.path.parent / "备份.sqlite3"
        self.ledger.backup(source)
        self.ledger.add("2026-10-11", 200, "当前内容")
        self.ledger.connection.close()
        self.ledger.connection = sqlite3.connect(f"{self.path.as_uri()}?mode=ro", uri=True)
        self.ledger.connection.row_factory = sqlite3.Row
        with self.assertRaises(sqlite3.OperationalError):
            self.ledger.restore(source)
        self.assertEqual([row["note"] for row in self.ledger.list_entries()], ["当前内容", "备份内容"])


if __name__ == "__main__":
    unittest.main()
