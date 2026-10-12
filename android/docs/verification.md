# Verification scope

[简体中文](#简体中文)

## Source-distribution checks, 2026-10-12

- Python unittest discovery ran against the public Android source copy: **77 tests passed**, using temporary databases. It covers exact six-decimal amounts and large IDs, persistence, CRUD, filtering, calendars, budgets, products, schema migrations, CSV, backup/restore, and explicit error paths.
- `tools/build.ps1` ran `assembleDebug` and `lintDebug` successfully in the original development project. These were incremental builds: assemble tasks were up to date; lint executed its final task. The generated lint XML has no error findings. This is not a clean build on a newly provisioned machine.
- The debug APK's signature verified with one signer using APK Signature Scheme v2. Package metadata confirmed version 1.0.0, package `cn.local.dailyledger`, minimum SDK 24, target SDK 35, `arm64-v8a`/`x86_64`, debug status, and no declared permissions.
- Official `zipalign -c -P 16 -v 4` verification passed. This verifies APK ZIP alignment; it does not establish runtime behavior on a 16 KB device.
- Source-copy hashes matched the original allowlisted source/build files. The Android ledger core and reused business tests matched the desktop copies. See [core provenance](core-provenance.md).

The Gradle invocation reported the experimental non-ASCII path override and Gradle deprecation warnings; assemble also reported an SDK XML tool-version warning. These did not fail the builds. Their originating configuration/dependency behavior was retained without changes.

The APK SHA256 is published with the release artifacts. Source distribution excludes local build caches/tools, device/user databases, backups, logs, screenshots, and generated audit reports.

## Browser checks and their boundary

The included preview server uses the actual Python API and a new temporary SQLite directory. The browser script checks CRUD and reopening, six-decimal precision, zero amounts, yearly calendar, monthly statistics, budgets, product subtotals, keyword filtering, full-month date ranges, text escaping, 360-pixel layout, and an explicit missing-native-bridge error. It also checks page initialization when a controlled pending-restore signal is cancelled.

These are component checks. The browser's Android bridge and pending-operation signals are controlled fixtures; they do not exercise Android's system file picker, content URI transfer, or Activity lifecycle. See [tools/README.md](../tools/README.md) to reproduce them.

## Device acceptance still required

Android 16/17 acceptance has not been completed. No connected phone or emulator was used for the source-distribution verification. The following remain unverified on Android:

- Actual startup and the embedded Python/SQLite runtime.
- Keyboard/insets, system back, rotation, foreground/background transitions, and process recreation.
- System file selection, cancellation, content URI copying, and document-result acknowledgement across Activity destruction.
- Old WebView versions, manufacturer-specific device transfer, and operation on an actual 16 KB page-size device.

The APK is debug-signed, not an app-store production build. An unreadable current database cannot be replaced through the existing normal restore flow. Restore's automatic pre-replacement backup lives in private storage without a dedicated mobile browsing/rollback interface. Unsubmitted page drafts are not guaranteed to survive process termination.

## Suggested first device check

1. Install and open the app. Save `33.662720`, close/reopen, and confirm the value is displayed as `33.66272`.
2. Edit and delete records; generate an amount from product quantity; inspect calendar and statistics updates.
3. Export a backup to an accessible location, add another record, restore the backup, and confirm whole-ledger replacement.
4. Cancel a file selection and select an invalid restore file; confirm no false success and no loss of current records.
5. Open the keyboard, use system back, rotate, switch foreground/background, and check operation state.

## 简体中文

### 2026-10-12 源码发布检查

- 对公开安卓源码副本运行 Python unittest：**77 项通过**，均使用临时数据库。覆盖精确六位小数和大 ID、持久化、增删改查、筛选、日历、预算、商品、模式迁移、CSV、备份/恢复及明确错误路径。
- 在原开发工程使用 `tools/build.ps1` 运行 `assembleDebug` 和 `lintDebug`，均成功。这是增量构建：assemble 任务均为最新，lint 执行了最终任务；生成的 lint XML 没有错误项。该证据不代表在全新配置机器上完成了干净构建。
- 开发 APK 通过签名验证：一个签名者，APK Signature Scheme v2。包信息确认版本 1.0.0、包名 `cn.local.dailyledger`、最低 SDK 24、target SDK 35、`arm64-v8a`/`x86_64`、debug 状态且未声明权限。
- 官方 `zipalign -c -P 16 -v 4` 检查通过。它验证 APK ZIP 对齐，不能证明应用在 16 KB 设备上的运行行为。
- 所有按清单复制的源码/构建文件与原工程哈希一致，安卓账本核心及复用业务测试与桌面副本一致，见[核心来源](core-provenance.md#简体中文)。

Gradle 执行中提示了非 ASCII 路径覆盖选项的实验性状态和弃用警告，assemble 还提示 SDK XML 工具版本警告。它们未导致构建失败；保留了对应配置/依赖行为，没有修改。

APK SHA256 随发布产物提供。公开源码不含本地缓存/工具、设备或用户数据库、备份、日志、截图及生成的审计报告。

### 浏览器检查及边界

预览服务器使用真实 Python API 和新建的临时 SQLite 目录。浏览器脚本检查增删改查和重新读取、六位小数精度、零金额、年度日历、月统计、预算、商品小计、关键词筛选、完整月份日期范围、文本转义、360 像素布局和缺少原生桥接时的明确错误；还检查受控待恢复信号被取消后的页面初始化。

这些属于组件检查。浏览器里的 Android 桥接和待处理信号是受控测试设施，没有执行 Android 系统文件选择器、content URI 传输或 Activity 生命周期。复现方式见 [tools/README.md](../tools/README.md#简体中文)。

### 仍需设备验收

尚未完成 Android 16/17 验收。本次源码发布验证未使用连接的手机或模拟器，以下 Android 行为仍未确认：

- 实际启动和内嵌 Python/SQLite 运行时。
- 输入法/窗口边距、系统返回、旋转、前后台切换和进程重建。
- 系统文件选择、取消、content URI 复制，以及 Activity 销毁后的文档结果确认。
- 旧版 WebView、厂商设备迁移和实际 16 KB 页设备运行。

APK 为开发签名版，非应用商店生产发布包。已经无法打开的当前数据库不能通过现有普通恢复流程替换。恢复前自动备份位于私有存储，尚无独立手机浏览/回滚界面。未提交的页面草稿不保证在进程结束后保留。

### 首次设备检查建议

1. 安装并打开，保存 `33.662720`，退出重开后确认显示为 `33.66272`。
2. 编辑、删除记录，通过商品数量生成金额，检查日历和统计更新。
3. 导出备份到可访问位置，新增另一笔，再恢复备份，确认整体替换正确。
4. 取消文件选择，并尝试无效恢复文件，确认没有虚假成功或当前记录丢失。
5. 打开键盘、使用系统返回、旋转和前后台切换，检查操作状态。
