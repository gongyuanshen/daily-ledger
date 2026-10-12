# Android API contract

[简体中文](#简体中文)

This contract describes `MainActivity.java`, `mobile_api.py`, and `assets/app.js`. It is a local in-process bridge, not an HTTP service in the installed app.

## Requests and values

```javascript
const result = JSON.parse(window.AndroidLedger.request(
  JSON.stringify({action: 'bootstrap', payload: {today: '2026-10-12'}})
));
```

`request` synchronously returns a JSON string containing `{ok:true,data:...}` or `{ok:false,error:{type,message}}`. Its top-level request object must contain exactly `action` (string) and `payload` (object). Python validates the boundary, invokes the ledger, logs failures with their traceback, and returns the error envelope. Java reports bridge failures visibly. The page must display failures rather than present fabricated data or success.

Money input is decimal text without thousands separators: an integer or a number with one to six fractional digits. Formatted API amounts have at least two and at most six fractional digits. Expense amounts and product prices accept zero; monthly budgets must be positive. The core stores integer millionths of a yuan. IDs are positive integer strings within SQLite's signed 64-bit range. Dates are strict `YYYY-MM-DD`; months are `YYYY-MM`. Counts, years, and quantities are JSON integers. Amount input crosses the bridge as text; JavaScript does not perform money arithmetic. Percentages are numeric display values only.

All fields listed below are required unless their values explicitly permit `null`. `filters` means `{start_day:null|string,end_day:null|string,category:null|string,payment:null|string,keyword:string}`.

| Action | Payload | Successful `data` |
|---|---|---|
| `bootstrap` | `{today}` | `{today,month,today_amount,today_count,month_amount,month_count,categories:[string],payments:[string],python_version,sqlite_version}` |
| `entries` | `filters` | `{entries:[{id,day,amount,note,category,payment}],amount,count}`; newest date/ID first |
| `save_entry` | `{id:null|string,day,amount,note,category,payment}` | `{id:string}`; `null` creates a record |
| `delete_entry` | `{id:string}` | `{deleted:true}` |
| `summary` | `{month}` | `{month,amount,count,daily_average,days_in_month,by_category:[{name,amount,percent}],by_day:[{day,amount,percent}],budget:null|string,remaining:null|string,over_budget}` |
| `calendar` | `{year:int}`; 1–9999 | `{year,amount,count,recorded_days,months:[{month,amount,count}],by_day:[{day,amount,count}]}` |
| `save_budget` | `{month,amount}`; amount > 0 | `{saved:true}` |
| `delete_budget` | `{month}` | `{deleted:true}` |
| `products` | `{}` | `{products:[{id,name,price}]}` |
| `save_product` | `{id:null|string,name,price}` | `{id:string}` |
| `delete_product` | `{id:string}` | `{deleted:true}` |
| `product_amount` | `{id:string,quantity:string,current_amount:string,add:bool}` | `{amount,description,quantity:int}` |

`summary.daily_average` divides by every day in the month and rounds to the nearest integer micro-unit. Category percentages use the monthly total; daily percentages use the highest daily amount (zero for an all-zero month). An unset budget returns `null` for both `budget` and `remaining`, and `"0.00"` for `over_budget`. `calendar.by_day` contains recorded days; the page displays an unrecorded day as `—` and a zero-value recorded day as `0.00`.

`product_amount.quantity` accepts integer text from 1 to 999999. With `add:false`, the current amount is ignored in the subtotal calculation, but remains a required valid amount string; the page passes `"0"`. The page fills the returned amount into the expense form, uses the description for an empty note, and appends it to an existing note in add mode. Product updates/deletion do not change expense history.

The page confirms destructive actions. After a successful save it closes the form and reports the committed save before refreshing; a subsequent refresh error does not relabel the save as failed.

## System documents and lifecycle

```javascript
window.AndroidLedger.documents(JSON.stringify({action: 'backup', payload: {}}));
```

`documents` returns `void` and opens the Android system picker. Actions are `backup`, `restore`, `csv`, and `logs`; CSV takes `filters`, and the other page calls pass `{}`. Completion calls `window.onDocumentResult(result)` with a JavaScript object:

- `{ok:true,action,data,message}`; an additional `warning` may expose a temporary-file cleanup error after the operation has committed.
- `{ok:false,action,error:{type,message}}`.
- `{cancelled:true,action}`; cancellation is not success.

The page confirms whole-ledger replacement before restore. A successful restore discards old forms and reloads the ledger. Python first inspects the selected file read-only, then preserves the current ledger in private `backups` and restores it. A current database which cannot be opened is outside this restore flow.

Native-only Python functions `export_file(data_directory,action,payload_json,destination_path)` and `restore_file(data_directory,source_path)` return the same JSON success/error envelope. Java copies between a system `content:` URI and a private temporary file. The web page cannot submit arbitrary filesystem paths. Transfer failures are reported; an unsuccessful Python export is never copied to the selected destination.

After registering `onDocumentResult`, the page calls `AndroidLedger.ready()`. `documentsPending()` reports an unfinished document operation; `onDocumentBusy(bool)` lets the page disable conflicting controls. The native layer retains pending document results until page acknowledgement. While restore is still being selected or processed, ledger requests fail explicitly. If the system ends the process during a document worker, the restored state reports an unconfirmed result and does not automatically repeat the operation.

The Android back action calls `window.handleAndroidBack()`: `true` means the page handled it; `false` allows the Activity to finish. Actual picker, lifecycle, and back behavior still require device acceptance.

## Local resource boundary

Java serves only packaged `index.html`, `style.css`, and `app.js` under `https://ledger.invalid/`. This is a synthetic local origin, not a remote server. Network loads, arbitrary file/content access, and unapproved page resources are blocked. The interface has no CDN dependencies. A missing `window.AndroidLedger` is shown as an environment error.

## 简体中文

本协议对应 `MainActivity.java`、`mobile_api.py` 和 `assets/app.js`，是本机进程内桥接；安装后的应用不提供 HTTP 服务。

### 请求和值

```javascript
const result = JSON.parse(window.AndroidLedger.request(
  JSON.stringify({action: 'bootstrap', payload: {today: '2026-10-12'}})
));
```

`request` 同步返回 JSON 字符串：`{ok:true,data:...}` 或 `{ok:false,error:{type,message}}`。顶层请求必须恰好包含字符串 `action` 和对象 `payload`。Python 在边界校验后调用账本，记录含堆栈的失败日志并返回错误；Java 明确展示桥接失败。页面必须展示失败，不能伪造数据或成功状态。

金额输入为不含千分位的十进制文本，接受整数或一到六位小数；API 格式化返回金额至少两位、最多六位小数。支出和商品单价可为零，月预算必须大于零。核心使用整数微元存储。ID 是 SQLite 有符号 64 位范围内的正整数文本；日期严格使用 `YYYY-MM-DD`，月份为 `YYYY-MM`。计数、年份和数量为 JSON 整数。金额输入以文本传递，JavaScript 不计算金额；数字百分比仅用于展示。

下表字段均为必填，除非字段值明确允许 `null`。`filters` 表示 `{start_day:null|string,end_day:null|string,category:null|string,payment:null|string,keyword:string}`。

| 操作 | payload | 成功的 `data` |
|---|---|---|
| `bootstrap` | `{today}` | `{today,month,today_amount,today_count,month_amount,month_count,categories:[string],payments:[string],python_version,sqlite_version}` |
| `entries` | `filters` | `{entries:[{id,day,amount,note,category,payment}],amount,count}`；日期/ID 降序 |
| `save_entry` | `{id:null|string,day,amount,note,category,payment}` | `{id:string}`；`null` 表示新增 |
| `delete_entry` | `{id:string}` | `{deleted:true}` |
| `summary` | `{month}` | `{month,amount,count,daily_average,days_in_month,by_category:[{name,amount,percent}],by_day:[{day,amount,percent}],budget:null|string,remaining:null|string,over_budget}` |
| `calendar` | `{year:int}`；1–9999 | `{year,amount,count,recorded_days,months:[{month,amount,count}],by_day:[{day,amount,count}]}` |
| `save_budget` | `{month,amount}`；金额 > 0 | `{saved:true}` |
| `delete_budget` | `{month}` | `{deleted:true}` |
| `products` | `{}` | `{products:[{id,name,price}]}` |
| `save_product` | `{id:null|string,name,price}` | `{id:string}` |
| `delete_product` | `{id:string}` | `{deleted:true}` |
| `product_amount` | `{id:string,quantity:string,current_amount:string,add:bool}` | `{amount,description,quantity:int}` |

`summary.daily_average` 按整月天数计算并四舍五入到整数微元。分类百分比使用当月总额；每日百分比使用最高日金额，全零月份为零。预算未设置时，`budget` 和 `remaining` 返回 `null`，`over_budget` 返回 `"0.00"`。`calendar.by_day` 仅包含有记录的日期，页面将无记录日期显示为 `—`，有零金额记录的日期显示为 `0.00`。

`product_amount.quantity` 接受 1 到 999999 的整数文本。`add:false` 时当前金额不参与小计，但仍须传有效金额文本，页面传 `"0"`。页面把结果金额填回支出表单；备注为空时使用商品描述，累加模式下向已有备注追加描述。商品修改或删除不改变历史支出。

页面先确认破坏性操作。保存成功后关闭表单并明确提示已经提交，再刷新页面；后续刷新失败不会被标为保存失败。

### 系统文档和生命周期

```javascript
window.AndroidLedger.documents(JSON.stringify({action: 'backup', payload: {}}));
```

`documents` 返回 `void` 并打开 Android 系统选择器。操作为 `backup`、`restore`、`csv`、`logs`；CSV 使用 `filters`，其他页面调用传 `{}`。完成后以 JavaScript 对象调用 `window.onDocumentResult(result)`：

- `{ok:true,action,data,message}`；如果操作已提交但临时文件清理失败，会额外返回 `warning` 明确提示。
- `{ok:false,action,error:{type,message}}`。
- `{cancelled:true,action}`；取消不代表成功。

恢复前页面确认整体替换。恢复成功后清空旧表单并重新读取账本。Python 先只读检查所选文件，再将当前账本保存到私有 `backups` 并恢复；当前数据库已经无法打开的情况不属于这条恢复流程。

仅供原生调用的 Python 函数 `export_file(data_directory,action,payload_json,destination_path)` 和 `restore_file(data_directory,source_path)` 返回同样的成功/失败 JSON 协议。Java 在系统 `content:` URI 与私有临时文件间复制，网页不能传任意文件路径。传输失败必须报告，Python 导出失败时不会把文件复制到所选目标。

页面注册 `onDocumentResult` 后调用 `AndroidLedger.ready()`。`documentsPending()` 表示文档操作未完成；`onDocumentBusy(bool)` 让页面禁用冲突操作。原生层保留待处理结果直到页面确认。恢复仍在选择或处理阶段时，账本请求会明确失败。若系统在文件处理线程工作期间结束进程，恢复状态会报告结果未确认，不自动重复操作。

Android 返回操作调用 `window.handleAndroidBack()`：`true` 表示页面已处理，`false` 允许 Activity 退出。实际系统选择器、生命周期和返回行为仍需设备验收。

### 本地资源边界

Java 仅在 `https://ledger.invalid/` 下提供打包的 `index.html`、`style.css` 和 `app.js`。这是合成的本地域，并非远程服务器。网络加载、任意 file/content 访问和未授权资源均被阻止，页面不依赖 CDN。缺失 `window.AndroidLedger` 会显示运行环境错误。
