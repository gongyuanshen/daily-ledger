param([string]$BuildPython = 'E:\Python\python.exe', [string]$Task = 'assembleDebug')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$jdkRoot = Join-Path $projectRoot '.tools\jdk17'
$sdkRoot = Join-Path $projectRoot '.tools\android-sdk'
foreach ($requiredPath in @("$jdkRoot\bin\java.exe", "$sdkRoot\platforms\android-35\android.jar", "$sdkRoot\build-tools\35.0.0\apksigner.bat", $BuildPython)) {
    if (!(Test-Path -LiteralPath $requiredPath)) { throw "Required build tool missing: $requiredPath. See tools/setup.ps1." }
}
$javaVersion = & "$jdkRoot\bin\java.exe" --version
if ($LASTEXITCODE -ne 0 -or ($javaVersion -join "`n") -notmatch '^openjdk 17\.') { throw "Build JDK must be version 17: $javaVersion" }
& $BuildPython -c 'import sys; assert sys.version_info[:2] == (3, 14), sys.version'
if ($LASTEXITCODE -ne 0) { throw 'Build Python must be version 3.14.' }
$env:JAVA_HOME = $jdkRoot
$env:ANDROID_HOME = $sdkRoot
$env:GRADLE_USER_HOME = Join-Path $projectRoot '.gradle'
$sdkProperty = $sdkRoot.Replace('\', '/').Replace(':', '\:')
[IO.File]::WriteAllText((Join-Path $projectRoot 'local.properties'), "sdk.dir=$sdkProperty`n", [Text.UTF8Encoding]::new($false))
Push-Location $projectRoot
try {
    & .\gradlew.bat $Task --console=plain "-Pledger.buildPython=$($BuildPython.Replace('\', '/'))"
    if ($LASTEXITCODE -ne 0) { throw "Gradle $Task failed with exit code $LASTEXITCODE." }
} finally { Pop-Location }
