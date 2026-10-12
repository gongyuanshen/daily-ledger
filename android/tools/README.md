# Windows build and verification tools

[简体中文](#简体中文)

Run commands from the repository's `android/` directory. The scripts preserve the existing project configuration: Java 17, Gradle 8.13, Android Gradle Plugin 8.13.0, Chaquopy 17.0.0, Python 3.14, Android platform 35, and build-tools 35.0.0.

## Set up and build

```powershell
powershell -ExecutionPolicy Bypass -File tools/setup.ps1
powershell -ExecutionPolicy Bypass -File tools/build.ps1 -BuildPython 'C:\Python314\python.exe'
```

`setup.ps1` downloads Microsoft OpenJDK 17, Gradle, and Android command-line tools from their official download endpoints. It accepts the SDK licenses required for this local build and installs platform-tools, platform 35, and build-tools 35.0.0. Downloads require network access; the installed app does not. The script verifies the pinned Gradle and Android command-line-tools archive SHA256 values. The JDK download URL is a rolling Microsoft JDK 17 endpoint.

Tools go under `.tools`, downloads under `.downloads`, and Gradle's cache under `.gradle`. The build script sets the toolchain environment for its process and writes an untracked `local.properties` containing the local SDK path; it does not change system-wide Java or SDK settings.

Install Python 3.14 separately and pass its actual executable via `-BuildPython`. Both `build.ps1` and the existing `ledger.buildPython` Gradle property default to `E:\Python\python.exe`. The parameter overrides that property for the invoked build. Missing tools or the wrong Python/JDK version cause an explicit error. Chaquopy packages Python for the phone; phone users need no Python installation.

The debug APK is written to `app/build/outputs/apk/debug/app-debug.apk`. This is a development-signed test build. Signing keys and local build outputs are not included in the public source tree. `android.overridePathCheck=true` is explicitly enabled for non-ASCII project paths and AGP reports it as experimental.

## Python tests and Android lint

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'app\src\main\python')
python -B -X utf8 -m unittest discover -s tests -v
powershell -ExecutionPolicy Bypass -File tools/build.ps1 -BuildPython 'C:\Python314\python.exe' -Task lintDebug
```

The tests create temporary databases. Expected invalid-input and database-failure cases print tracebacks while asserting explicit failure responses. They do not read a user's installed-app ledger.

After building, with the script-provided SDK and JDK:

```powershell
$env:JAVA_HOME = (Join-Path (Get-Location) '.tools\jdk17')
& '.tools\android-sdk\build-tools\35.0.0\apksigner.bat' verify --verbose 'app\build\outputs\apk\debug\app-debug.apk'
& '.tools\android-sdk\build-tools\35.0.0\zipalign.exe' -c -P 16 -v 4 'app\build\outputs\apk\debug\app-debug.apk'
& '.tools\android-sdk\platform-tools\adb.exe' devices
```

ZIP alignment and signature checks are static checks. Real device acceptance is still required.

## Optional browser verification

The browser script requires Node.js 20 or newer, a locally installed Chrome, and `playwright-core` in the exact local directory used by the script. The verified development dependency was version 1.64.0:

```powershell
npm install --prefix .tools/browser-check playwright-core@1.64.0
New-Item -ItemType Directory -Force artifacts | Out-Null
python -B -X utf8 tools/preview_server.py --port 8765 --data 'C:\Temp\daily-ledger-ui-new'
```

Use a **new, nonexistent** directory for `--data`; the server refuses an existing directory. Keep that terminal open. In another terminal, from `android/`:

```powershell
node tools/verify_ui.cjs
```

The server binds to `127.0.0.1:8765` and serves the actual local assets and Python API using the new temporary SQLite ledger. Screenshots are written to `artifacts`. Stop the server with Ctrl+C when finished. These checks exercise page behavior and controlled native-bridge signals; Android's file picker, URI transfer, WebView runtime, and Activity lifecycle require device tests. The preview server and browser tools are not packaged in the APK.

## 简体中文

### Windows 构建和验证工具

请从仓库的 `android/` 目录运行命令。脚本保留现有工程配置：Java 17、Gradle 8.13、Android Gradle Plugin 8.13.0、Chaquopy 17.0.0、Python 3.14、Android 平台 35 和 build-tools 35.0.0。

### 安装工具并构建

```powershell
powershell -ExecutionPolicy Bypass -File tools/setup.ps1
powershell -ExecutionPolicy Bypass -File tools/build.ps1 -BuildPython 'C:\Python314\python.exe'
```

`setup.ps1` 从官方下载地址获取 Microsoft OpenJDK 17、Gradle 和 Android command-line tools，接受本次本机构建需要的 SDK 许可，并安装 platform-tools、平台 35 和 build-tools 35.0.0。下载需要联网，安装后的记账应用无需联网。脚本对固定的 Gradle 和 Android command-line-tools 压缩包校验 SHA256；JDK 使用 Microsoft 提供的滚动 JDK 17 下载地址。

工具放在 `.tools`，下载包放在 `.downloads`，Gradle 缓存放在 `.gradle`。构建脚本只为自身进程设置工具链环境，并生成含本地 SDK 路径且不纳入版本控制的 `local.properties`；不修改系统 Java 或全局 SDK 设置。

请另外安装 Python 3.14，并通过 `-BuildPython` 传入实际可执行文件路径。现有 `build.ps1` 和 `ledger.buildPython` Gradle 属性均默认指向 `E:\Python\python.exe`；该参数会覆盖本次构建的属性。工具缺失或 Python/JDK 版本不符会明确报错。Chaquopy 会为手机打包 Python，手机用户无需安装 Python。

开发签名 APK 输出到 `app/build/outputs/apk/debug/app-debug.apk`，用于安装测试。公开源码不包含签名密钥和本机构建产物。工程通过 `android.overridePathCheck=true` 显式支持非 ASCII 工程路径，AGP 会将该选项提示为实验性配置。

### Python 测试和 Android lint

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'app\src\main\python')
python -B -X utf8 -m unittest discover -s tests -v
powershell -ExecutionPolicy Bypass -File tools/build.ps1 -BuildPython 'C:\Python314\python.exe' -Task lintDebug
```

测试会创建临时数据库。无效输入和数据库故障用例会输出预期的异常堆栈，同时断言明确的失败响应；不会读取用户安装后的真实账本。

构建完成后，可使用脚本安装的 SDK 和 JDK 检查：

```powershell
$env:JAVA_HOME = (Join-Path (Get-Location) '.tools\jdk17')
& '.tools\android-sdk\build-tools\35.0.0\apksigner.bat' verify --verbose 'app\build\outputs\apk\debug\app-debug.apk'
& '.tools\android-sdk\build-tools\35.0.0\zipalign.exe' -c -P 16 -v 4 'app\build\outputs\apk\debug\app-debug.apk'
& '.tools\android-sdk\platform-tools\adb.exe' devices
```

ZIP 对齐和签名验证属于静态检查，仍需真机验收。

### 可选浏览器验证

浏览器脚本需要 Node.js 20 或更新版本、本机 Chrome，以及放在脚本指定本地目录的 `playwright-core`。已验证的开发依赖版本为 1.64.0：

```powershell
npm install --prefix .tools/browser-check playwright-core@1.64.0
New-Item -ItemType Directory -Force artifacts | Out-Null
python -B -X utf8 tools/preview_server.py --port 8765 --data 'C:\Temp\daily-ledger-ui-new'
```

`--data` 必须指向**尚不存在的新目录**；服务器拒绝复用现有目录。保持该终端运行，在另一终端从 `android/` 运行：

```powershell
node tools/verify_ui.cjs
```

服务器监听 `127.0.0.1:8765`，使用真实本地页面、Python 接口和新建的临时 SQLite 账本。截图写入 `artifacts`。完成后用 Ctrl+C 停止服务器。这些检查验证页面行为与受控原生桥接信号；Android 文件选择器、URI 传输、WebView 运行时和 Activity 生命周期仍需设备测试。预览服务器和浏览器工具不打包进 APK。
