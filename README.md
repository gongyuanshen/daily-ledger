# Daily Ledger · 日常记账

English | [简体中文](#简体中文)

A local RMB expense tracker for Windows and Android. Enter each expense once; the app calculates daily, monthly, and yearly totals. Each version keeps its own SQLite database.

## Downloads

Open [v1.0.0 downloads](https://github.com/gongyuanshen/daily-ledger/releases/tag/v1.0.0).

| Platform | Download | Requirements |
| --- | --- | --- |
| Android | [`daily-ledger-1.0.0-android-debug.apk`](https://github.com/gongyuanshen/daily-ledger/releases/download/v1.0.0/daily-ledger-1.0.0-android-debug.apk) | Android 7.0 / API 24 or newer; arm64-v8a or x86_64; Android System WebView |
| Windows | [`daily-ledger-1.0.0-windows-source.zip`](https://github.com/gongyuanshen/daily-ledger/releases/download/v1.0.0/daily-ledger-1.0.0-windows-source.zip) | Python with Tkinter, SQLite 3.37+, and CustomTkinter 6.0.0; verified with Python 3.14.4 |
| Integrity | [`SHA256SUMS.txt`](https://github.com/gongyuanshen/daily-ledger/releases/download/v1.0.0/SHA256SUMS.txt) | SHA-256 checksums for both downloads |

The Android download is a debug-signed development build. Android 16/17 device acceptance is pending. The Windows download contains runnable source and requires Python. Documentation is available in English first and Chinese second; the current application interfaces use Chinese.

## Start using it

**Android:** transfer the APK to your phone, open it with the file manager, allow installation when prompted, and launch 日常记账. See the [Android guide](android/README.md) for requirements, backup, and build instructions.

**Windows:** extract the ZIP to a writable folder. Open PowerShell in that folder and run:

```powershell
python -m pip install -r requirements.txt
python app.py
```

When working from a clone, run these commands inside `desktop/`. After installing dependencies, you can also double-click `启动记账.cmd`. See the [Windows guide](desktop/README.md).

## Features

- Add, edit, and delete expenses; filter by date, category, payment method, and keyword.
- Store RMB amounts as integer micro-yuan, preserving up to six decimal places, including zero-value entries.
- Browse an annual expense calendar, daily trends, and category totals.
- Set monthly budgets and view remaining or exceeded amounts.
- Manage product prices and calculate expense amounts from quantities.
- Export filtered CSV records and back up or restore the complete SQLite ledger.
- Display input, database, and file errors with explicit messages.

## Data and transfer

Both versions work locally without an account or server. The Android manifest requests no network permission. There is no automatic synchronization between devices.

Windows stores its ledger in `data/ledger.sqlite3` beside the program. Android stores it in app-private storage. Transfer a ledger by exporting a SQLite backup on one device and restoring it on the other. Restore replaces the entire ledger, including budgets and products. Export a backup before uninstalling Android or changing devices.

Personal ledgers, private import records, backups, logs, local toolchains, and signing keys are excluded from this repository and its downloads.

## Source and checks

| Path | Contents |
| --- | --- |
| [`desktop/`](desktop/README.md) | Windows UI, ledger core, and tests |
| [`android/`](android/README.md) | Android project, local WebView UI, embedded Python core, and tests |
| [`android/docs/api-contract.md`](android/docs/api-contract.md) | Mobile bridge and JSON contract |
| [`android/docs/core-provenance.md`](android/docs/core-provenance.md) | Shared-core provenance |
| [`android/docs/verification.md`](android/docs/verification.md) | Android validation scope and device acceptance checklist |
| [`docs/releases/v1.0.0.md`](docs/releases/v1.0.0.md) | Bilingual release notes |

Run the Windows tests from `desktop/`:

```powershell
python -X utf8 -m unittest discover -v
```

Run the Android Python tests from `android/`:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'app/src/main/python')
python -X utf8 -m unittest discover -s tests -v
```

These tests use temporary ledgers. Browser checks and static APK checks have a narrower scope than Android device testing. See the component guides for build details and known limitations.

## 简体中文

一个在 Windows 和 Android 本地运行的人民币支出记账工具。每笔消费输入一次，自动计算每日、每月和全年合计。两个版本分别保存自己的 SQLite 账本。

### 下载

打开 [v1.0.0 下载页](https://github.com/gongyuanshen/daily-ledger/releases/tag/v1.0.0)。

| 平台 | 下载文件 | 运行要求 |
| --- | --- | --- |
| Android | [`daily-ledger-1.0.0-android-debug.apk`](https://github.com/gongyuanshen/daily-ledger/releases/download/v1.0.0/daily-ledger-1.0.0-android-debug.apk) | Android 7.0 / API 24 及以上，arm64-v8a 或 x86_64，Android System WebView |
| Windows | [`daily-ledger-1.0.0-windows-source.zip`](https://github.com/gongyuanshen/daily-ledger/releases/download/v1.0.0/daily-ledger-1.0.0-windows-source.zip) | 包含 Tkinter 的 Python、SQLite 3.37+、CustomTkinter 6.0.0；已使用 Python 3.14.4 验证 |
| 文件校验 | [`SHA256SUMS.txt`](https://github.com/gongyuanshen/daily-ledger/releases/download/v1.0.0/SHA256SUMS.txt) | 两个下载文件的 SHA-256 校验值 |

安卓下载包是 debug 签名的开发版，Android 16/17 真机验收尚未完成。Windows 下载包包含可运行源码，需要安装 Python。说明文档默认展示英文，后附中文；当前应用界面使用中文。

### 开始使用

**Android：**把 APK 传到手机，在文件管理器中打开，按系统提示允许安装，然后启动「日常记账」。运行要求、备份和构建步骤见 [安卓版说明](android/README.md#简体中文)。

**Windows：**把 ZIP 解压到可写目录，在该目录打开 PowerShell 并运行：

```powershell
python -m pip install -r requirements.txt
python app.py
```

如果使用克隆的仓库，请在 `desktop/` 中执行上述命令。依赖安装后也可以双击 `启动记账.cmd`。详见 [桌面版说明](desktop/README.md#简体中文)。

### 功能

- 新增、修改、删除支出，按日期、分类、支付方式和关键词筛选。
- 人民币金额用整数微元保存，保留最多六位小数，支持零支出记录。
- 年度支出日历、每日趋势和分类汇总。
- 月度预算、剩余额度和超出金额。
- 商品单价管理和按数量计算记账金额。
- 按当前筛选导出 CSV，完整备份和恢复 SQLite 账本。
- 对输入、数据库和文件错误显示明确提示。

### 数据保存与迁移

两个版本均在本地工作，不需要账号或服务器。Android 清单没有申请网络权限。不同设备之间不会自动同步。

Windows 把账本保存在程序旁的 `data/ledger.sqlite3`，Android 使用应用私有存储。跨设备迁移时，在一端导出 SQLite 备份，再到另一端恢复。恢复会整体替换账本、预算和商品。卸载安卓应用或换机前请导出备份。

仓库和下载包均排除个人账本、私有导入记录、备份、日志、本地工具链和签名密钥。

### 源码与验证

| 路径 | 内容 |
| --- | --- |
| [`desktop/`](desktop/README.md#简体中文) | Windows 界面、账本核心和测试 |
| [`android/`](android/README.md#简体中文) | 安卓工程、本地 WebView 界面、内嵌 Python 核心和测试 |
| [`android/docs/api-contract.md`](android/docs/api-contract.md) | 手机桥接接口与 JSON 约定 |
| [`android/docs/core-provenance.md`](android/docs/core-provenance.md) | 复用核心的来源 |
| [`android/docs/verification.md`](android/docs/verification.md) | 安卓验证范围与真机验收清单 |
| [`docs/releases/v1.0.0.md`](docs/releases/v1.0.0.md) | 双语版本说明 |

桌面测试在 `desktop/` 中运行：

```powershell
python -X utf8 -m unittest discover -v
```

安卓 Python 测试在 `android/` 中运行：

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'app/src/main/python')
python -X utf8 -m unittest discover -s tests -v
```

测试使用临时账本。浏览器验证和 APK 静态检查的范围小于 Android 真机测试，构建细节及已知限制见各版本说明。
