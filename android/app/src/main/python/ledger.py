"""金额解析与本地 SQLite 账本；金额全程使用整数微元。"""
import csv
import re
import sqlite3
import tempfile
from calendar import monthrange
from contextlib import closing
from datetime import date, datetime
from pathlib import Path


CATEGORIES = ("未分类", "餐饮", "交通", "购物", "居住", "娱乐", "医疗", "教育", "通讯", "其他")
PAYMENTS = ("未指定", "微信", "支付宝", "银行卡", "现金", "其他")
AMOUNT_SCALE = 1_000_000
MAX_DECIMAL_PLACES = 6
_MAX_INTEGER = 9223372036854775807
_LEGACY_EXPENSES_SQL = """
    CREATE TABLE expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        day TEXT NOT NULL,
        amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
        note TEXT NOT NULL
    ) STRICT
"""
_V1_EXPENSES_SQL = """
    CREATE TABLE expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        day TEXT NOT NULL,
        amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
        note TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT '未分类',
        payment TEXT NOT NULL DEFAULT '未指定'
    ) STRICT
"""
_V1_BUDGETS_SQL = """
    CREATE TABLE budgets (
        month TEXT PRIMARY KEY,
        amount_cents INTEGER NOT NULL CHECK (amount_cents > 0)
    ) STRICT
"""
_EXPENSES_SQL = """
    CREATE TABLE expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        day TEXT NOT NULL,
        amount_units INTEGER NOT NULL CHECK (amount_units >= 0),
        note TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT '未分类',
        payment TEXT NOT NULL DEFAULT '未指定'
    ) STRICT
"""
_BUDGETS_SQL = """
    CREATE TABLE budgets (
        month TEXT PRIMARY KEY,
        amount_units INTEGER NOT NULL CHECK (amount_units > 0)
    ) STRICT
"""
_PRODUCTS_SQL = """
    CREATE TABLE products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE CHECK (length(trim(name)) > 0 AND name = trim(name)),
        price_units INTEGER NOT NULL CHECK (price_units >= 0)
    ) STRICT
"""


def parse_amount(text: str) -> int:
    value = text.strip()
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]{1,6})?", value):
        raise ValueError("请输入大于或等于 0 的金额，最多六位小数，例如 33.662720。")
    whole, _, fraction = value.partition(".")
    whole = whole.lstrip("0") or "0"
    if len(whole) > 13:
        raise ValueError("金额超出 SQLite 可保存的整数范围。")
    amount_units = int(whole) * AMOUNT_SCALE + int(fraction.ljust(MAX_DECIMAL_PLACES, "0"))
    if amount_units > _MAX_INTEGER:
        raise ValueError("金额超出 SQLite 可保存的整数范围。")
    return amount_units


def parse_day(text: str) -> str:
    value = text.strip()
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("日期格式应为 YYYY-MM-DD，例如 2026-10-10。")
    try:
        date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"日期不存在：{value}。请检查年月日。") from error
    return value


def format_amount(amount_units: int) -> str:
    sign = "-" if amount_units < 0 else ""
    amount_units = abs(amount_units)
    fraction = f"{amount_units % AMOUNT_SCALE:06d}".rstrip("0").ljust(2, "0")
    return f"{sign}{amount_units // AMOUNT_SCALE:,}.{fraction}"


def _parse_month(month: str) -> str:
    value = month.strip()
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}", value):
        raise ValueError("月份格式应为 YYYY-MM，例如 2026-10。")
    parse_day(f"{value}-01")
    return value


class Ledger:
    def __init__(self, path: Path):
        self.path = Path(path).resolve()
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        try:
            version, is_empty = self._check_schema(self.connection, allow_empty=True)
            if version == 3:
                return
            if not is_empty:
                backup_directory = self.path.parent / "backups"
                backup_directory.mkdir(exist_ok=True)
                self.backup(backup_directory / (
                    f"{self.path.stem}-before-v3-{datetime.now():%Y%m%d-%H%M%S-%f}.sqlite3"
                ))
            with self.connection:
                self.connection.execute("BEGIN IMMEDIATE")
                if is_empty:
                    self.connection.execute(_EXPENSES_SQL)
                    self.connection.execute(_BUDGETS_SQL)
                elif version < 2:
                    multiplier = AMOUNT_SCALE // 100
                    for table, key in (("expenses", "id"), ("budgets", "month")):
                        if table == "budgets" and version == 0:
                            continue
                        overflow = self.connection.execute(
                            f"SELECT {key}, amount_cents FROM {table} WHERE amount_cents > ? LIMIT 1",
                            (_MAX_INTEGER // multiplier,),
                        ).fetchone()
                        if overflow is not None:
                            raise ValueError(f"旧账本 {table} 记录 {overflow[0]} 的金额 {overflow[1]} 分"
                                             "转换为微元后超出 SQLite 整数范围，升级未执行。")
                    sequence = self.connection.execute(
                        "SELECT seq FROM sqlite_sequence WHERE name = 'expenses'"
                    ).fetchone()
                    self.connection.execute("ALTER TABLE expenses RENAME TO expenses_legacy")
                    self.connection.execute(_EXPENSES_SQL)
                    metadata = "category, payment" if version == 1 else "'未分类', '未指定'"
                    self.connection.execute(
                        "INSERT INTO expenses (id, day, amount_units, note, category, payment) "
                        f"SELECT id, day, amount_cents * {multiplier}, note, {metadata} FROM expenses_legacy"
                    )
                    self.connection.execute("DROP TABLE expenses_legacy")
                    if sequence is not None:
                        cursor = self.connection.execute(
                            "UPDATE sqlite_sequence SET seq = MAX(seq, ?) WHERE name = 'expenses'", (sequence[0],)
                        )
                        if cursor.rowcount == 0:
                            self.connection.execute("INSERT INTO sqlite_sequence (name, seq) VALUES ('expenses', ?)",
                                                    (sequence[0],))
                    if version == 1:
                        self.connection.execute("ALTER TABLE budgets RENAME TO budgets_legacy")
                    self.connection.execute(_BUDGETS_SQL)
                    if version == 1:
                        self.connection.execute(
                            f"INSERT INTO budgets SELECT month, amount_cents * {multiplier} FROM budgets_legacy"
                        )
                        self.connection.execute("DROP TABLE budgets_legacy")
                self.connection.execute(_PRODUCTS_SQL)
                self.connection.execute("CREATE INDEX IF NOT EXISTS expenses_day ON expenses(day)")
                self.connection.execute("PRAGMA user_version = 3")
        except Exception:
            self.connection.close()
            raise

    @staticmethod
    def _check_schema(connection: sqlite3.Connection, allow_empty: bool = False) -> tuple[int, bool]:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1, 2, 3):
            raise ValueError(f"账本版本 {version} 不受支持，数据库未修改。")
        objects = connection.execute(
            "SELECT type, name, sql FROM sqlite_master WHERE name NOT GLOB 'sqlite_*'"
        ).fetchall()
        tables = {row[1]: row[2] for row in objects if row[0] == "table"}
        if not objects and version == 0 and allow_empty:
            return version, True
        expected_tables = {"expenses"} if version == 0 else {"expenses", "budgets"}
        if version == 3:
            expected_tables.add("products")
        if set(tables) != expected_tables or any(row[0] not in ("table", "index") for row in objects):
            raise ValueError("数据库不是受支持的记账账本。")
        if any(row[0] == "index" and row[1] != "expenses_day" for row in objects):
            raise ValueError("账本含有未知索引，不能安全使用。")
        for index in connection.execute("PRAGMA index_list(expenses)"):
            if tuple(index)[1:] != ("expenses_day", 0, "c", 0):
                raise ValueError("账本日期索引含有未知约束。")
            if [row[2] for row in connection.execute("PRAGMA index_info(expenses_day)")] != ["day"]:
                raise ValueError("账本日期索引结构不受支持。")
        strict_tables = {row[1] for row in connection.execute("PRAGMA table_list") if row[5] == 1}
        if not expected_tables <= strict_tables:
            raise ValueError("账本表必须使用 SQLite STRICT 数据类型约束。")
        expected_columns = [
            ("id", "INTEGER", 0, None, 1),
            ("day", "TEXT", 1, None, 0),
            ("amount_units" if version >= 2 else "amount_cents", "INTEGER", 1, None, 0),
            ("note", "TEXT", 1, None, 0),
        ]
        if version >= 1:
            expected_columns.extend([
                ("category", "TEXT", 1, "'未分类'", 0),
                ("payment", "TEXT", 1, "'未指定'", 0),
            ])
        actual_columns = [tuple(row)[1:] for row in connection.execute("PRAGMA table_info(expenses)")]
        if actual_columns != expected_columns:
            raise ValueError("账本支出表结构不受支持。")
        expected_sql = {"expenses": _EXPENSES_SQL if version >= 2 else (_LEGACY_EXPENSES_SQL, _V1_EXPENSES_SQL)[version],
                        "budgets": _BUDGETS_SQL if version >= 2 else _V1_BUDGETS_SQL,
                        "products": _PRODUCTS_SQL}
        for table in expected_tables:
            compact_sql = re.sub(r"\s+", "", tables[table]).upper()
            if compact_sql != re.sub(r"\s+", "", expected_sql[table]).upper():
                raise ValueError(f"账本 {table} 表含有不受支持的结构或约束。")
        if version >= 1:
            budget_columns = [tuple(row)[1:] for row in connection.execute("PRAGMA table_info(budgets)")]
            if budget_columns != [("month", "TEXT", 1, None, 1),
                                  ("amount_units" if version >= 2 else "amount_cents", "INTEGER", 1, None, 0)]:
                raise ValueError("账本预算表结构不受支持。")
        if version == 3:
            product_columns = [tuple(row)[1:] for row in connection.execute("PRAGMA table_info(products)")]
            if product_columns != [("id", "INTEGER", 0, None, 1), ("name", "TEXT", 1, None, 0),
                                   ("price_units", "INTEGER", 1, None, 0)]:
                raise ValueError("账本商品表结构不受支持。")
        return version, False

    def _separate_file(self, path: Path) -> Path:
        path = Path(path).resolve()
        if path == self.path or (path.exists() and path.samefile(self.path)):
            raise ValueError("该操作不能使用当前账本文件作为来源或目标。")
        return path

    def backup(self, destination: Path) -> None:
        destination = self._separate_file(destination)
        with closing(sqlite3.connect(destination)) as target:
            self.connection.backup(target)

    @staticmethod
    def _check_backup(connection: sqlite3.Connection) -> None:
        integrity = [row[0] for row in connection.execute("PRAGMA integrity_check")]
        if integrity != ["ok"]:
            raise ValueError(f"备份文件完整性检查失败：{'；'.join(integrity)}")
        version, _ = Ledger._check_schema(connection)
        for row in connection.execute("SELECT id, day FROM expenses"):
            if parse_day(row[1]) != row[1]:
                raise ValueError(f"备份中记录 {row[0]} 的日期不是规范的 YYYY-MM-DD 格式。")
        if version >= 1:
            for row in connection.execute("SELECT month FROM budgets"):
                if _parse_month(row[0]) != row[0]:
                    raise ValueError(f"备份中的预算月份 {row[0]} 格式不规范。")
        if version == 3:
            for row in connection.execute("SELECT id, name, price_units FROM products"):
                name, _ = Ledger._validate_product(row[1], row[2])
                if name != row[1]:
                    raise ValueError(f"备份中的商品 {row[0]} 名称含有未清理的首尾空白。")

    def restore(self, source: Path) -> None:
        source = self._separate_file(source)
        with tempfile.TemporaryDirectory(prefix="ledger-restore-") as directory:
            candidate = Path(directory) / "账本.sqlite3"
            with closing(sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True)) as saved:
                saved.execute("BEGIN")
                self._check_backup(saved)
                with closing(sqlite3.connect(candidate)) as temporary:
                    saved.backup(temporary)
            with closing(Ledger(candidate)) as normalized:
                self._check_backup(normalized.connection)
                normalized.connection.backup(self.connection)

    def export_csv(self, destination: Path, rows: list[sqlite3.Row]) -> None:
        destination = self._separate_file(destination)
        def safe_text(value: str) -> str:
            dangerous = ("=", "+", "-", "@", "＝", "＋", "－", "＠")
            if value.startswith(("\t", "\r", "\n")) or value.lstrip(" \t\r\n\v\f\ufeff").startswith(dangerous):
                return "'" + value
            return value

        with destination.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(("日期", "金额", "分类", "支付方式", "备注"))
            for row in rows:
                writer.writerow((safe_text(row["day"]), format_amount(row["amount_units"]).replace(",", ""),
                                 safe_text(row["category"]), safe_text(row["payment"]),
                                 safe_text(row["note"])))

    def add(self, day: str, amount_units: int, note: str,
            category: str = "未分类", payment: str = "未指定") -> int:
        with self.connection:
            cursor = self.connection.execute(
                "INSERT INTO expenses (day, amount_units, note, category, payment) VALUES (?, ?, ?, ?, ?)",
                (day, amount_units, note, category, payment),
            )
        return cursor.lastrowid

    def update(self, record_id: int, day: str, amount_units: int, note: str,
               category: str | None = None, payment: str | None = None) -> None:
        fields = ["day = ?", "amount_units = ?", "note = ?"]
        values = [day, amount_units, note]
        if category is not None:
            fields.append("category = ?")
            values.append(category)
        if payment is not None:
            fields.append("payment = ?")
            values.append(payment)
        with self.connection:
            cursor = self.connection.execute(
                f"UPDATE expenses SET {', '.join(fields)} WHERE id = ?",
                (*values, record_id),
            )
            if cursor.rowcount != 1:
                raise LookupError(f"记录 {record_id} 不存在，修改未保存。")

    def delete(self, record_id: int) -> None:
        with self.connection:
            cursor = self.connection.execute("DELETE FROM expenses WHERE id = ?", (record_id,))
            if cursor.rowcount != 1:
                raise LookupError(f"记录 {record_id} 不存在，删除未执行。")

    def list_day(self, day: str) -> list[sqlite3.Row]:
        return self.connection.execute(
            "SELECT id, day, amount_units, note FROM expenses WHERE day = ? ORDER BY id DESC",
            (day,),
        ).fetchall()

    def list_entries(self, start_day: str | None = None, end_day: str | None = None,
                     category: str | None = None, payment: str | None = None,
                     keyword: str = "") -> list[sqlite3.Row]:
        start_day = parse_day(start_day) if start_day is not None else None
        end_day = parse_day(end_day) if end_day is not None else None
        if start_day is not None and end_day is not None and start_day > end_day:
            raise ValueError("开始日期不能晚于结束日期。")
        conditions, values = [], []
        for column, operator, value in (
            ("day", ">=", start_day), ("day", "<=", end_day),
            ("category", "=", category), ("payment", "=", payment),
        ):
            if value is not None:
                conditions.append(f"{column} {operator} ?")
                values.append(value)
        if keyword:
            conditions.append("(instr(note, ?) > 0 OR instr(category, ?) > 0 OR instr(payment, ?) > 0)")
            values.extend([keyword] * 3)
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        return self.connection.execute(
            "SELECT id, day, amount_units, note, category, payment FROM expenses"
            f"{where} ORDER BY day DESC, id DESC", values,
        ).fetchall()

    def categories(self) -> list[str]:
        existing = {row[0] for row in self.connection.execute("SELECT DISTINCT category FROM expenses")}
        return list(CATEGORIES) + sorted(existing.difference(CATEGORIES))

    def payments(self) -> list[str]:
        existing = {row[0] for row in self.connection.execute("SELECT DISTINCT payment FROM expenses")}
        return list(PAYMENTS) + sorted(existing.difference(PAYMENTS))

    def month_summary(self, month: str) -> dict:
        month = _parse_month(month)
        year, number = map(int, month.split("-"))
        rows = self.list_entries(f"{month}-01", f"{month}-{monthrange(year, number)[1]:02d}")
        by_category, by_day = {}, {}
        for row in rows:
            amount = row["amount_units"]
            if amount > 0:
                by_category[row["category"]] = by_category.get(row["category"], 0) + amount
            by_day[row["day"]] = by_day.get(row["day"], 0) + amount
        return {
            "total_units": sum(row["amount_units"] for row in rows), "count": len(rows),
            "by_category": sorted(by_category.items(), key=lambda item: (-item[1], item[0])),
            "by_day": dict(sorted(by_day.items())),
        }

    def year_summary(self, year: int) -> dict:
        if type(year) is not int or not 1 <= year <= 9999:
            raise ValueError("年份必须是 1 至 9999 之间的整数。")
        rows = self.list_entries(f"{year:04d}-01-01", f"{year:04d}-12-31")
        by_day = {}
        for row in rows:
            by_day[row["day"]] = by_day.get(row["day"], 0) + row["amount_units"]
        return {
            "total_units": sum(row["amount_units"] for row in rows), "count": len(rows),
            "by_day": dict(sorted(by_day.items())),
        }

    def get_budget(self, month: str) -> int | None:
        row = self.connection.execute("SELECT amount_units FROM budgets WHERE month = ?",
                                      (_parse_month(month),)).fetchone()
        return row[0] if row is not None else None

    def set_budget(self, month: str, amount_units: int) -> None:
        month = _parse_month(month)
        with self.connection:
            self.connection.execute("""
                INSERT INTO budgets (month, amount_units) VALUES (?, ?)
                ON CONFLICT(month) DO UPDATE SET amount_units = excluded.amount_units
            """, (month, amount_units))

    def clear_budget(self, month: str) -> None:
        with self.connection:
            self.connection.execute("DELETE FROM budgets WHERE month = ?", (_parse_month(month),))

    @staticmethod
    def _validate_product(name: str, price_units: int) -> tuple[str, int]:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("商品名称不能为空。")
        if type(price_units) is not int or not 0 <= price_units <= _MAX_INTEGER:
            raise ValueError("商品价格必须是 SQLite 整数范围内的非负整数微元。")
        return name.strip(), price_units

    def list_products(self) -> list[sqlite3.Row]:
        return self.connection.execute("SELECT id, name, price_units FROM products ORDER BY name, id").fetchall()

    def get_product(self, product_id: int) -> sqlite3.Row:
        row = self.connection.execute("SELECT id, name, price_units FROM products WHERE id = ?",
                                      (product_id,)).fetchone()
        if row is None:
            raise LookupError(f"商品 {product_id} 不存在。")
        return row

    def add_product(self, name: str, price_units: int) -> int:
        name, price_units = self._validate_product(name, price_units)
        try:
            with self.connection:
                cursor = self.connection.execute("INSERT INTO products (name, price_units) VALUES (?, ?)",
                                                 (name, price_units))
        except sqlite3.IntegrityError as error:
            if error.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_UNIQUE:
                raise ValueError(f"商品名称“{name}”已存在。") from error
            raise
        return cursor.lastrowid

    def update_product(self, product_id: int, name: str, price_units: int) -> None:
        name, price_units = self._validate_product(name, price_units)
        try:
            with self.connection:
                cursor = self.connection.execute("UPDATE products SET name = ?, price_units = ? WHERE id = ?",
                                                 (name, price_units, product_id))
                if cursor.rowcount != 1:
                    raise LookupError(f"商品 {product_id} 不存在，修改未保存。")
        except sqlite3.IntegrityError as error:
            if error.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_UNIQUE:
                raise ValueError(f"商品名称“{name}”已存在。") from error
            raise

    def delete_product(self, product_id: int) -> None:
        with self.connection:
            cursor = self.connection.execute("DELETE FROM products WHERE id = ?", (product_id,))
            if cursor.rowcount != 1:
                raise LookupError(f"商品 {product_id} 不存在，删除未执行。")

    def close(self) -> None:
        self.connection.close()
