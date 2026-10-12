# Daily Ledger for Android

[简体中文](#简体中文)

An offline RMB expense tracker with a Chinese interface. A Java Activity hosts a local WebView, and Chaquopy packages the same Python/SQLite ledger core used by the [desktop component](../desktop/README.md). No account, server, or separate Python installation is needed on the phone.

## Install

Download the Android APK from [GitHub Releases](https://github.com/gongyuanshen/daily-ledger/releases), transfer it to your phone, and open it with the phone's file manager. Allow installation from that file manager if Android asks. Save one test expense, close the app, and reopen it to check persistence.

Version 1.0.0 is a **debug-signed installation test build**, not an app-store release. Its package ID is `cn.local.dailyledger`. Minimum Android version is 7.0 (API 24); compile/target SDK is 35. The APK includes `arm64-v8a` and `x86_64`, with no 32-bit runtime. It needs an available Android System WebView. Android 16/17 device acceptance remains outstanding; SDK settings and static alignment checks do not establish device compatibility.

## Features

- Add, edit, delete, and filter expenses by date, category, payment method, or keyword. Keywords search notes, categories, and payment methods.
- Record nonnegative RMB amounts with up to six decimal places. Calculations and storage use integer millionths of a yuan.
- View a yearly calendar, daily/monthly/yearly totals, category statistics, and daily trends. A day without records differs from a day with a zero-value record.
- Set a monthly budget and view the remaining amount or overspend.
- Manage product unit prices and use a quantity to replace or add to an expense amount. Later product edits do not change recorded expenses.
- Export a full SQLite backup, restore a backup, export the current filtered view as CSV, or export error logs through Android's system file picker.
- See explicit errors. A committed save and a failed subsequent page refresh are reported separately.

## Data and desktop migration

The first launch creates an empty ledger in the app's private storage. Desktop and Android maintain separate databases; there is no automatic sync. The APK contains no user ledger or expense history, requests no network permission, and blocks WebView network loads. Android system backup is disabled in the manifest; manufacturer-specific device transfer has not been verified.

To move desktop data to Android:

1. In the desktop app, use `数据备份 → 保存备份` to export a `.sqlite3` file.
2. Transfer that file to your phone.
3. In Android, use `更多 → 恢复账本`, confirm replacement, and select the file.

Restore validates the selected backup, preserves the current mobile ledger under the private `backups` directory, and replaces the whole ledger. It does not merge databases. Automatic backups currently have no separate mobile browsing or rollback screen, so export a backup to an accessible location before an important restore.

The existing restore flow requires the current database to be readable. It cannot directly repair a current ledger which is already too corrupt to open; preserve its files for separate investigation. Uninstalling deletes app-private data, so export a backup before uninstalling or changing phones. Unsubmitted drafts use page session storage and are not guaranteed to survive process termination.

## Build and verify

The supplied build scripts run on Windows. See [tools/README.md](tools/README.md) for toolchain setup, the Python path override, and optional browser checks.

```powershell
powershell -ExecutionPolicy Bypass -File tools/setup.ps1
powershell -ExecutionPolicy Bypass -File tools/build.ps1 -BuildPython 'C:\Python314\python.exe'
powershell -ExecutionPolicy Bypass -File tools/build.ps1 -BuildPython 'C:\Python314\python.exe' -Task lintDebug
$env:PYTHONPATH = (Join-Path (Get-Location) 'app\src\main\python')
python -B -X utf8 -m unittest discover -s tests -v
```

Run these commands from `android/`. Supply your actual Python 3.14 executable; the existing script and Gradle property default to `E:\Python\python.exe`. Build output is `app/build/outputs/apk/debug/app-debug.apk`. The app bundles Python, so this build-time requirement does not apply to phones.

| Path | Purpose |
|---|---|
| `app/src/main/assets` | Local mobile page, styles, and interaction |
| `app/src/main/java` | Android host, Python bridge, system file operations |
| `app/src/main/python` | Shared ledger core and Android JSON boundary |
| `tests` | Business/API tests using temporary ledgers |
| `tools` | Windows build and browser verification scripts |
| `docs` | [API contract](docs/api-contract.md), [core provenance](docs/core-provenance.md), and [verification scope](docs/verification.md) |

Local tools, caches, build output, databases, logs, and generated verification artifacts are excluded from the source distribution. APKs are distributed through Releases.

## 简体中文

离线人民币支出记账应用，当前界面为中文。Java Activity 承载本地 WebView，Chaquopy 打包与[桌面版](../desktop/README.md)相同的 Python/SQLite 账本核心。手机无需账号、服务器或额外安装 Python。

### 安装

从 [GitHub Releases](https://github.com/gongyuanshen/daily-ledger/releases) 下载安卓版 APK，传到手机并用文件管理器打开。如 Android 提示，请允许该文件管理器安装应用。先保存一笔测试支出，关闭应用后重新打开，检查记录是否保留。

1.0.0 是**开发签名的安装测试版**，尚未上架应用商店。包名为 `cn.local.dailyledger`；最低 Android 7.0（API 24），compile/target SDK 35。APK 提供 `arm64-v8a` 和 `x86_64`，不含 32 位运行库，需要可用的 Android System WebView。Android 16/17 真机验收尚未完成；SDK 配置和静态对齐检查不能证明设备兼容性。

### 功能

- 新增、编辑、删除支出；按日期、分类、支付方式和关键词筛选。关键词搜索备注、分类和支付方式。
- 支持非负人民币金额，最多六位小数；计算和存储均使用整数微元。
- 年度日历、每日/每月/全年汇总、分类统计与每日趋势。无记录的日期与有零金额记录的日期分开展示。
- 设置月预算，查看剩余额度和超出金额。
- 管理商品单价，按数量替换或累加到记账金额；商品后续改价不改变历史支出。
- 通过 Android 系统文件选择器导出完整 SQLite 备份、恢复备份、按当前筛选导出 CSV 或导出错误日志。
- 明确显示错误；已经提交的保存与后续页面刷新失败分别提示。

### 数据和桌面迁移

首次启动会在应用私有存储创建空账本。桌面版和安卓版分别保存数据，不会自动同步。APK 不含用户账本或消费记录，不申请网络权限，WebView 也禁止网络加载。清单中关闭了 Android 系统备份；厂商设备迁移行为尚未验证。

从桌面版迁移数据：

1. 在桌面版使用 `数据备份 → 保存备份`，导出 `.sqlite3` 文件。
2. 把该文件传到手机。
3. 在安卓版使用 `更多 → 恢复账本`，确认整体替换并选择文件。

恢复会先验证所选备份，把当前手机账本保存到应用私有 `backups` 目录，再整体替换；不会合并两份账本。自动备份目前没有独立的手机浏览或回滚界面，因此重要恢复前请先导出一份到可访问的位置。

现有恢复流程要求当前数据库能够打开，不能直接修复已经损坏到无法打开的当前账本；请保留原文件另行排查。卸载会删除应用私有数据，换机或卸载前请导出备份。未提交草稿使用页面会话存储，不保证系统结束应用进程后仍然保留。

### 构建和验证

现有构建脚本运行于 Windows。工具安装、Python 路径参数和可选浏览器检查见 [tools/README.md](tools/README.md#简体中文)。

```powershell
powershell -ExecutionPolicy Bypass -File tools/setup.ps1
powershell -ExecutionPolicy Bypass -File tools/build.ps1 -BuildPython 'C:\Python314\python.exe'
powershell -ExecutionPolicy Bypass -File tools/build.ps1 -BuildPython 'C:\Python314\python.exe' -Task lintDebug
$env:PYTHONPATH = (Join-Path (Get-Location) 'app\src\main\python')
python -B -X utf8 -m unittest discover -s tests -v
```

在 `android/` 目录运行，Python 参数应替换为实际的 Python 3.14 路径。现有脚本和 Gradle 属性默认指向 `E:\Python\python.exe`。构建产物为 `app/build/outputs/apk/debug/app-debug.apk`。Python 已打包进应用，手机没有这项构建环境要求。

| 路径 | 用途 |
|---|---|
| `app/src/main/assets` | 本地手机页面、样式与交互 |
| `app/src/main/java` | Android 外壳、Python 桥接与系统文件操作 |
| `app/src/main/python` | 共用账本核心与安卓 JSON 边界 |
| `tests` | 使用临时账本的业务和接口测试 |
| `tools` | Windows 构建和浏览器验证脚本 |
| `docs` | [接口协议](docs/api-contract.md#简体中文)、[核心来源](docs/core-provenance.md#简体中文)和[验证范围](docs/verification.md#简体中文) |

源代码发布不含本机构建工具、缓存、构建输出、数据库、日志或生成的验证产物。APK 通过 Releases 提供。
