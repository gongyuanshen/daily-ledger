# Ledger core provenance

[简体中文](#简体中文)

The Android core at [`app/src/main/python/ledger.py`](../app/src/main/python/ledger.py) is an unchanged copy of the repository's [desktop `ledger.py`](../../desktop/ledger.py). The original Android copy was made on 2026-10-11; byte equality was checked again for this source distribution on 2026-10-12.

SHA256 for both copies:

```text
28BC6935CF6FD7D5B0C7D8356EE70428AB1E3879494AF171032A5B89179F3CD7
```

The core owns amount/date rules, expense and product operations, monthly budgets, SQLite schema migration, CSV export, and full database backup/restore. It does not import a GUI toolkit. Android adds `mobile_api.py` for its JSON boundary, local HTML/CSS/JavaScript for the interface, and `MainActivity.java` for the host and system document operations.

The desktop business tests `test_ledger.py`, `test_ledger_features.py`, and `test_product_ledger.py` are reused unchanged in Android's `tests/`; `test_mobile_api.py` exercises the Android boundary. The source package contains no desktop GUI, user database, imported history, backups, or logs. Each platform maintains its own ledger; backup transfer is explicit and there is no automatic synchronization.

## 简体中文

安卓核心 [`app/src/main/python/ledger.py`](../app/src/main/python/ledger.py) 是仓库[桌面版 `ledger.py`](../../desktop/ledger.py) 的原样副本。安卓副本最初于 2026-10-11 创建，本次源码发布于 2026-10-12 再次确认字节完全一致。

两份文件的 SHA256：

```text
28BC6935CF6FD7D5B0C7D8356EE70428AB1E3879494AF171032A5B89179F3CD7
```

核心负责金额/日期规则、支出与商品操作、月预算、SQLite 模式迁移、CSV 导出和完整数据库备份/恢复，不导入 GUI 工具包。安卓通过 `mobile_api.py` 添加 JSON 边界，使用本地 HTML/CSS/JavaScript 提供界面，并由 `MainActivity.java` 承载应用和系统文档操作。

桌面业务测试 `test_ledger.py`、`test_ledger_features.py` 和 `test_product_ledger.py` 原样复用于安卓 `tests/`，`test_mobile_api.py` 验证安卓接口边界。源码包不含桌面 GUI、用户数据库、导入记录、备份或日志。两端分别持有账本，通过明确的备份传输迁移，不会自动同步。
