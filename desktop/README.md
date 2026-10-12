# Daily Ledger — Windows desktop

[English](#english) · [简体中文](#简体中文)

## English

Daily Ledger is a local Windows expense tracker for recording individual expenses in Chinese yuan (RMB). It automatically summarizes daily and monthly spending and keeps the ledger on your computer. The application interface is in Simplified Chinese; this documentation is bilingual.

### Requirements and installation

The validated environment is **Python 3.14.4**, **Tk 8.6**, **SQLite 3.50.4**, and **CustomTkinter 6.0.0**. Python must include `tkinter`, and its bundled SQLite must be **3.37 or newer**, because the database uses `STRICT` tables. Other Python versions have not been verified for this release.

This desktop release distributes source files and requires Python. A standalone Windows EXE is not provided.

Open PowerShell in this `desktop` folder and run:

```powershell
python -m pip install -r requirements.txt
python app.py
```

Once Python and the dependency are installed, you can also double-click **启动记账.cmd**. The launcher runs `python app.py` from its own folder, so the `python` command must be available on `PATH`.

For a runtime check:

```powershell
python -c "import sys, sqlite3, tkinter, customtkinter; print(sys.version); print('SQLite', sqlite3.sqlite_version); print('Tk', tkinter.TkVersion); print('CustomTkinter', customtkinter.__version__)"
```

Use a folder where your Windows account can write files: the application creates its `data` folder next to `app.py`.

### Add, edit, and delete expenses

1. Enter an amount in the right-hand form, such as `25.50` or `33.662720`. Zero expenses are allowed. Amounts accept up to six decimal places and are stored as integer micro-yuan: **1 yuan = 1,000,000 units**. Accepted input is preserved exactly rather than rounded. Inputs with more than six decimal places, negative values, exponent notation, or thousands separators are rejected. Displayed amounts show at least two decimals and omit unnecessary trailing zeros.
2. Choose the expense date by clicking the date field or calendar button. The picker supports previous/next month, year and month selection, and today. You can also enter `YYYY-MM-DD` manually.
3. Choose a category and payment method, or type your own names. Use **未分类** (uncategorized) and **未指定** (unspecified) when appropriate; neither field may be empty.
4. Add an optional note and click **保存支出** (save expense), or press Enter in the amount or note field. The saved expense appears in that day's records.
5. Select a record and click **修改** (edit), or double-click it. **取消修改** (cancel edit) leaves the saved record unchanged. The top **+ 记一笔** (add an expense) button starts a new entry.
6. Select a record, click **删除** (delete), and confirm to remove it. Deletion cannot be undone from the interface.

### Products and quick entry

- Open **商品管理** (products), enter a unique product name and unit price, and click **保存商品** (save product). Select a product to edit or delete it. Unit prices allow zero and up to six decimal places.
- In the expense form, click **选择商品** (choose product), select a product, and enter an integer quantity from 1 to 999999. Review the unit price and subtotal, then choose **计入金额** to replace the amount or **累加到金额** to add the subtotal to the current amount. You can add several products in succession.
- Product selection fills the form; it creates an expense only when you click **保存支出**. You may adjust the amount manually. An empty note is filled with the product name and quantity; an existing custom note is retained. Adding a product subtotal appends its description to the note.
- Changing a product price or deleting a product leaves previously saved expense amounts unchanged.

### Find records, review spending, and export

- **账本明细** (ledger): choose a day, month, all records, or a custom date range. Combine these with category, payment method, and keyword filters. Keywords search notes, categories, and payment methods. Click **筛选** (filter) or press Enter in the search field to submit.
- **支出日历** (expense calendar): view all twelve months in three columns, switch years with the arrows, enter a year and click **查看** (view) or press Enter, or click **今年** (this year). The header shows the year's total, record count, and number of days with records. Each month shows a total, and each date shows the sum of all expenses on that date, with up to six decimal places.
- In the calendar, **—** means no records and **0.00** means one or more records totaling zero. Scroll vertically through the year; long amounts can be viewed by horizontal scrolling. Clicking a date opens all of that day's records and clears the ledger filters while preserving the unsaved amount and note in the entry form. Reopening the calendar reloads its totals from the ledger.
- Choosing a query date through the date picker submits the query immediately. After typing a date manually, press Enter. For a custom start/end range, click **筛选** after filling both dates.
- The ledger header shows today's spending, the current calendar month's spending, and the total and record count for the current filters. Click table headers to sort; amounts are sorted numerically.
- **统计分析** (statistics): choose any date in a month to see that whole month's total, record count, daily average, daily trend, and category shares. The daily average uses all calendar days in the month.
- **预算管理** (budgets): save or remove a monthly budget, and review spending, remaining budget, and overspending for the whole month. Budgets must be greater than zero. Ledger filters do not change budget calculations.
- **导出 CSV** (export CSV): export the current ledger list with date, amount, category, payment method, and note columns. The file uses UTF-8 with a BOM for opening in Excel. To export all records, choose **全部** (all) and clear the other filters first. CSV is an export format; there is no CSV import interface.

### Local storage, backups, and errors

- Successful saves commit immediately to `data\ledger.sqlite3` beside the application. The folder and database are created on first launch, and records persist after closing and reopening the app. The database location follows the application folder rather than the PowerShell working directory.
- Under **数据备份** (data backups), click **保存备份** (save backup) to create a SQLite file containing all expenses, budgets, and products while the application is running.
- **从备份恢复** (restore backup) replaces the current expenses, budgets, and products after confirmation. Before restoring, the app saves the current ledger in `data\backups`. It validates the selected backup and reports invalid, corrupt, or unsupported files.
- Before upgrading a supported older ledger, the app automatically saves the original database in `data\backups`. Legacy amounts stored in cents are converted exactly to micro-yuan, preserving their monetary value.
- When moving the application, keep the entire application folder, including `data`. Keep backups in a safe location: SQLite database files and CSV exports are not encrypted.
- Invalid input produces a specific warning. Database and file failures produce an error dialog with context; detailed tracebacks are written to `data\errors.log`. If a database change committed but refreshing the display failed, the message states that the change was saved or restored. Query the ledger again before deciding whether to repeat an operation.

There is no account login, online service, or automatic synchronization. Windows and Android store their ledgers separately; running both versions does not synchronize their data.

### Verify the desktop component

Run the bundled tests from this folder:

```powershell
python -B -m unittest discover -v
```

The suite uses real Tk widgets and temporary or in-memory SQLite databases, so it requires a Windows desktop session. It does not write test expenses to your active ledger. Confirmation and notification dialogs are controlled by the tests; SQLite commit, rollback, persistence, and failure checks use real databases. These automated checks do not replace trying the application on your own display and Python installation.

## 简体中文

日常记账是一款 Windows 本地支出记账软件。逐笔输入人民币支出，自动汇总每天和每月花费，账本保存在电脑上。软件界面为简体中文，本文档提供完整的英文和中文说明。

### 运行环境与安装

已验证环境为 **Python 3.14.4**、**Tk 8.6**、**SQLite 3.50.4** 和 **CustomTkinter 6.0.0**。Python 必须包含 `tkinter`，其内置 SQLite 版本必须为 **3.37 或以上**，因为账本使用 `STRICT` 表。此版本尚未验证其他 Python 版本。

当前桌面版本以源码形式发布，需要安装 Python，尚未提供可独立运行的 Windows EXE。

在本 `desktop` 文件夹中打开 PowerShell，运行：

```powershell
python -m pip install -r requirements.txt
python app.py
```

安装 Python 和依赖后，也可双击 **启动记账.cmd**。启动脚本在自身所在目录执行 `python app.py`，因此 `python` 命令必须能通过 `PATH` 找到。

可使用以下命令检查运行环境：

```powershell
python -c "import sys, sqlite3, tkinter, customtkinter; print(sys.version); print('SQLite', sqlite3.sqlite_version); print('Tk', tkinter.TkVersion); print('CustomTkinter', customtkinter.__version__)"
```

请将软件放在当前 Windows 账户有写入权限的文件夹中；程序会在 `app.py` 旁创建 `data` 文件夹。

### 新增、修改与删除支出

1. 在右侧表单输入金额，例如 `25.50` 或 `33.662720`。允许零支出，最多六位小数。金额以整数微元保存，**1 元 = 1,000,000 微元**，合法输入的金额会精确保留，不会四舍五入。超过六位小数、负数、科学计数法或带千位分隔符的输入会被拒绝。显示时至少保留两位小数，并省略多余的末尾零。
2. 点击消费日期或日历按钮选择日期。日期选择器支持前后月、年份和月份选择以及今天，也可手动填写 `YYYY-MM-DD`。
3. 选择消费分类与支付方式，支持直接输入自定义名称。未确定时选择 **未分类** 和 **未指定**，这两个字段不能留空。
4. 可填写备注，点击 **保存支出**，也可以在金额或备注框按 Enter。保存后显示该日记录。
5. 选中明细点击 **修改**，或双击记录。**取消修改** 保留原记录，顶部 **+ 记一笔** 进入新增模式。
6. 选中明细点击 **删除**，确认后删除。界面不提供删除撤销功能。

### 商品管理与快速记账

- 在 **商品管理** 输入不重复的商品名称和单价，点击 **保存商品**。选中商品可修改或删除。单价允许为零，最多六位小数。
- 在记账表单金额旁点击 **选择商品**，选择商品并填写整数数量（1～999999）。核对单价和小计后，点击 **计入金额** 替换金额，或点击 **累加到金额** 将小计加入当前金额，可逐次累加多种商品。
- 商品选择只填写表单，点击 **保存支出** 才会入账。金额仍可手动调整。空备注会填写商品名称和数量，已有自定义备注予以保留；累加商品时会追加商品说明。
- 商品改价或删除后，已保存的支出金额保持原值。

### 查询、统计与导出

- **账本明细**：支持当天、本月、全部和自定义日期范围，可组合分类、支付方式和关键词筛选。关键词搜索备注、分类及支付方式。点击 **筛选** 或在搜索框按 Enter 提交。
- **支出日历**：十二个月按三列排列。使用前后年按钮切换，输入年份点击 **查看** 或按 Enter，点击 **今年** 返回当前年。顶部显示年度合计、笔数和记账天数，每月显示月合计，每个日期显示当天全部支出的合计，最多保留六位小数。
- 日历中的 **—** 表示没有记录，**0.00** 表示已有一笔或多笔记录且合计为零。可纵向滚动查看全年，金额较长时可横向滚动。点击日期会进入当天全部明细并清除明细筛选条件，同时保留右侧未保存的金额和备注。每次重新打开日历都会从账本重新汇总。
- 使用日期选择器选择查询日期后立即查询；手动填写日期后按 Enter 提交。自定义起止日期填写完成后点击 **筛选**。
- 明细页顶部显示今日、本月和当前筛选结果的金额，以及筛选结果笔数。点击表头可排序，金额按数值排序。
- **统计分析**：选择某月任意日期，显示整月总支出、笔数、日均金额、每日趋势和分类占比。日均金额按该月完整天数计算。
- **预算管理**：按月保存或移除预算，查看整月支出、剩余额度和超出金额。预算必须大于零，明细筛选不会改变预算统计。
- **导出 CSV**：导出当前明细列表，包含日期、金额、分类、支付方式和备注，采用带 BOM 的 UTF-8 编码，支持 Excel 打开。导出全部记录前，选择 **全部** 并清除其他筛选。CSV 用于导出，软件没有 CSV 导入界面。

### 本地数据、备份与错误提示

- 每次成功保存都会立即提交到程序目录下的 `data\ledger.sqlite3`。首次启动时创建文件夹和数据库，关闭再打开记录仍在。账本位置取决于程序所在目录，不受 PowerShell 工作目录影响。
- 在 **数据备份** 页点击 **保存备份**，可在软件运行时保存包含全部支出、预算和商品的 SQLite 文件。
- **从备份恢复** 会在确认后替换当前支出、预算和商品。恢复前先将当前账本保存到 `data\backups`，并验证所选备份。无效、损坏或不支持的备份会明确报错。
- 升级受支持的旧账本前，程序会自动将原账本备份到 `data\backups`。原来以分保存的金额会精确转换为微元，金额数值保持不变。
- 移动软件时，请保留整个软件文件夹，包括 `data`。妥善保管备份；SQLite 账本文件和 CSV 导出文件没有加密。
- 输入不合法时会显示具体提示。数据库或文件出错时会显示带上下文的错误窗口，详细 traceback 保存于 `data\errors.log`。如果账本已提交但显示刷新失败，提示会明确告知已保存或已恢复。请先重新查询账本，再决定是否重复操作。

软件没有账户登录、在线服务或自动同步。Windows 和 Android 分别保存本地账本，同时使用两个版本不会自动同步数据。

### 验证桌面组件

在本文件夹运行随附测试：

```powershell
python -B -m unittest discover -v
```

测试使用真实 Tk 控件以及临时或内存 SQLite 数据库，需要 Windows 桌面会话，不会向使用中的账本写入测试支出。确认和提示对话框由测试控制；数据库提交、回滚、持久化和失败验证使用真实 SQLite。自动化检查不能替代在自己的显示环境和 Python 安装中实际试用软件。
