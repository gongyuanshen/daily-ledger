import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from ledger import Ledger, format_amount, parse_amount, parse_day


class InputTests(unittest.TestCase):
    def test_amounts_are_parsed_as_exact_integer_units(self):
        cases = {
            "0": 0,
            "0.00": 0,
            "0.000000": 0,
            "0.000001": 1,
            "0.01": 10000,
            "0.10": 100000,
            "0.20": 200000,
            "1": 1000000,
            "1.2": 1200000,
            "1.2345": 1234500,
            "1.23456": 1234560,
            " 1234.56 ": 1234560000,
            "33.662720": 33662720,
            "45.986": 45986000,
            "00033.662720": 33662720,
            "9223372036854.775807": 9223372036854775807,
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                result = parse_amount(value)
                self.assertIsInstance(result, int)
                self.assertEqual(result, expected)

    def test_invalid_amounts_are_rejected(self):
        cases = (
            "", " ", "-1", "-0", "-0.000001", "1.0000001", "0.0000000",
            "+1", ".5", "1.",
            "NaN", "nan", "inf", "Infinity", "1e2", "1E2",
            "1,000.00", "1_000", "1 00", "abc",
            "9223372036854.775808", "9223372036855", "9" * 5000,
        )
        for value in cases:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_amount(value)

    def test_valid_dates_are_normalized_without_changing_the_day(self):
        for value, expected in (
            ("2026-10-10", "2026-10-10"),
            (" 2024-02-29 ", "2024-02-29"),
        ):
            with self.subTest(value=value):
                self.assertEqual(parse_day(value), expected)

    def test_invalid_dates_and_other_iso_formats_are_rejected(self):
        cases = (
            "", " ", "2026-02-29", "2024-02-30", "2026-13-01",
            "2026-00-10", "2026-10-00", "2026-1-10", "2026-10-1",
            "20261010", "2026-W41-6", "2026/10/10", "2026-10-10T00:00:00",
        )
        for value in cases:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_day(value)

    def test_amount_formatting_is_exact_including_large_daily_totals(self):
        cases = {
            0: "0.00",
            1: "0.000001",
            10: "0.00001",
            100: "0.0001",
            1000: "0.001",
            10000: "0.01",
            300000: "0.30",
            1200000: "1.20",
            1234560000: "1,234.56",
            33662720: "33.66272",
            45986000: "45.986",
            9223372036854775807: "9,223,372,036,854.775807",
            18446744073709551614: "18,446,744,073,709.551614",
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(format_amount(value), expected)


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="ledger-test-")
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "账本.sqlite3"
        self.ledger = Ledger(self.path)
        self.addCleanup(lambda: self.ledger.close())

    def test_add_keeps_days_separate_and_returns_newest_records_first(self):
        first = self.ledger.add("2026-10-10", parse_amount("0.10"), "早餐")
        second = self.ledger.add("2026-10-10", parse_amount("0.20"), "")
        other = self.ledger.add("2026-10-11", 700, "另一天")

        rows = self.ledger.list_day("2026-10-10")
        self.assertEqual([row["id"] for row in rows], [second, first])
        self.assertTrue(all(isinstance(row, sqlite3.Row) for row in rows))
        self.assertEqual([row["day"] for row in rows], ["2026-10-10"] * 2)
        self.assertEqual([row["note"] for row in rows], ["", "早餐"])
        self.assertEqual(sum(row["amount_units"] for row in rows), 300000)
        other_rows = self.ledger.list_day("2026-10-11")
        self.assertEqual([row["id"] for row in other_rows], [other])
        self.assertEqual(other_rows[0]["amount_units"], 700)
        self.assertEqual(self.ledger.list_day("2026-10-12"), [])

    def test_update_moves_the_record_and_preserves_its_id(self):
        changed = self.ledger.add("2026-10-10", 1250, "原备注")
        unchanged = self.ledger.add("2026-10-10", 100, "保留")

        self.ledger.update(changed, "2026-10-11", 999, "修改后")

        old_day = self.ledger.list_day("2026-10-10")
        self.assertEqual([row["id"] for row in old_day], [unchanged])
        self.assertEqual(sum(row["amount_units"] for row in old_day), 100)
        new_day = self.ledger.list_day("2026-10-11")
        self.assertEqual(len(new_day), 1)
        self.assertEqual(dict(new_day[0]), {
            "id": changed, "day": "2026-10-11",
            "amount_units": 999, "note": "修改后",
        })

    def test_delete_removes_only_the_selected_record(self):
        deleted = self.ledger.add("2026-10-10", 1250, "删除")
        retained = self.ledger.add("2026-10-10", 250, "保留")

        self.ledger.delete(deleted)

        rows = self.ledger.list_day("2026-10-10")
        self.assertEqual([row["id"] for row in rows], [retained])
        self.assertEqual(sum(row["amount_units"] for row in rows), 250)
        self.ledger.delete(retained)
        self.assertEqual(self.ledger.list_day("2026-10-10"), [])

    def test_writes_are_committed_before_returning_and_survive_reopening(self):
        with closing(sqlite3.connect(self.path)) as observer:
            record_id = self.ledger.add("2026-10-10", 1234, "中文备注 ' ?")
            self.assertEqual(observer.execute(
                "SELECT day, amount_units, note FROM expenses WHERE id = ?",
                (record_id,),
            ).fetchone(), ("2026-10-10", 1234, "中文备注 ' ?"))

            self.ledger.update(record_id, "2026-10-11", 5678, "更新")
            self.assertEqual(observer.execute(
                "SELECT day, amount_units, note FROM expenses WHERE id = ?",
                (record_id,),
            ).fetchone(), ("2026-10-11", 5678, "更新"))

            deleted = self.ledger.add("2026-10-11", 100, "删除")
            self.ledger.delete(deleted)
            self.assertEqual(observer.execute(
                "SELECT COUNT(*) FROM expenses WHERE id = ?", (deleted,),
            ).fetchone()[0], 0)

        self.ledger.close()
        self.ledger = Ledger(self.path)
        rows = self.ledger.list_day("2026-10-11")
        self.assertEqual(len(rows), 1)
        self.assertEqual(dict(rows[0]), {
            "id": record_id, "day": "2026-10-11",
            "amount_units": 5678, "note": "更新",
        })
        self.assertEqual(self.ledger.list_day("2026-10-10"), [])

    def test_missing_record_update_and_delete_raise_instead_of_succeeding(self):
        record_id = self.ledger.add("2026-10-10", 100, "保留")
        with self.assertRaises(LookupError):
            self.ledger.update(record_id + 1, "2026-10-11", 200, "不存在")
        with self.assertRaises(LookupError):
            self.ledger.delete(record_id + 1)
        self.assertEqual(len(self.ledger.list_day("2026-10-10")), 1)
        self.assertEqual(self.ledger.list_day("2026-10-11"), [])

    def test_database_accepts_zero_amount_for_add_and_update(self):
        record_id = self.ledger.add("2026-10-10", amount_units=0, note="零支出")
        self.assertEqual(self.ledger.list_day("2026-10-10")[0]["amount_units"], 0)
        self.ledger.update(record_id, "2026-10-11", 1, "最小微元")
        self.ledger.update(record_id, "2026-10-11", amount_units=0, note="归零")
        self.assertEqual(self.ledger.list_day("2026-10-11")[0]["amount_units"], 0)
        self.assertEqual(self.ledger.list_day("2026-10-10"), [])

    def test_database_rejects_negative_null_and_noninteger_amounts(self):
        for value in (-1, None, 1.5):
            with self.subTest(value=value):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.ledger.add("2026-10-10", value, "非法金额")
                self.assertEqual(self.ledger.list_day("2026-10-10"), [])

    def test_six_decimal_expenses_and_int64_boundary_survive_reopening(self):
        self.ledger.add("2026-10-10", parse_amount("33.662720"), "六位小数")
        self.ledger.add("2026-10-10", parse_amount("45.986"), "三位小数")
        self.ledger.add("2026-10-11", parse_amount("9223372036854.775807"), "上限")
        self.ledger.close()
        self.ledger = Ledger(self.path)
        rows = self.ledger.list_day("2026-10-10")
        self.assertEqual([row["amount_units"] for row in rows], [45986000, 33662720])
        self.assertEqual(format_amount(sum(row["amount_units"] for row in rows)), "79.64872")
        self.assertEqual(self.ledger.list_day("2026-10-11")[0]["amount_units"], 9223372036854775807)

    def test_invalid_amount_update_preserves_existing_record(self):
        record_id = self.ledger.add("2026-10-10", 1, "原记录")
        for value in (-1, None, 1.5):
            with self.subTest(value=value):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.ledger.update(record_id, "2026-10-11", value, "不应保存")
                self.assertEqual(dict(self.ledger.list_day("2026-10-10")[0]), {
                    "id": record_id, "day": "2026-10-10",
                    "amount_units": 1, "note": "原记录",
                })
                self.assertEqual(self.ledger.list_day("2026-10-11"), [])

    def test_real_readonly_write_errors_propagate_without_changing_records(self):
        record_id = self.ledger.add("2026-10-10", 100, "原记录")
        self.ledger.connection.execute("PRAGMA query_only = ON")
        operations = (
            ("add", lambda: self.ledger.add("2026-10-11", 200, "新记录")),
            ("update", lambda: self.ledger.update(
                record_id, "2026-10-11", 200, "修改")),
            ("delete", lambda: self.ledger.delete(record_id)),
        )
        for name, operation in operations:
            with self.subTest(operation=name):
                with self.assertRaises(sqlite3.OperationalError) as caught:
                    operation()
                self.assertEqual(caught.exception.sqlite_errorcode, sqlite3.SQLITE_READONLY)
                rows = self.ledger.list_day("2026-10-10")
                self.assertEqual(len(rows), 1)
                self.assertEqual(dict(rows[0]), {
                    "id": record_id, "day": "2026-10-10",
                    "amount_units": 100, "note": "原记录",
                })
                self.assertEqual(self.ledger.list_day("2026-10-11"), [])


if __name__ == "__main__":
    unittest.main()
