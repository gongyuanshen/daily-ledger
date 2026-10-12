$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$projectRoot = Split-Path -Parent $PSScriptRoot
$toolsRoot = Join-Path $projectRoot '.tools'
$downloadsRoot = Join-Path $projectRoot '.downloads'
New-Item -ItemType Directory -Force -Path $toolsRoot, $downloadsRoot | Out-Null
$packages = @(
    @{ Name='jdk17.zip'; Url='https://aka.ms/download-jdk/microsoft-jdk-17-windows-x64.zip' },
    @{ Name='gradle8.13.zip'; Url='https://services.gradle.org/distributions/gradle-8.13-bin.zip' },
    @{ Name='android-tools.zip'; Url='https://dl.google.com/android/repository/commandlinetools-win-15859902_latest.zip' }
)
foreach ($package in $packages) {
    $archivePath = Join-Path $downloadsRoot $package.Name
    if (!(Test-Path -LiteralPath $archivePath)) {
        Invoke-WebRequest -UseBasicParsing -Uri $package.Url -OutFile "$archivePath.part"
        Move-Item -LiteralPath "$archivePath.part" -Destination $archivePath
    }
}
$androidArchive = Join-Path $downloadsRoot 'android-tools.zip'
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $androidArchive).Hash -ne '90AE805D20434428BFFCB699C290860F19BB5F66A67E6B330067E3DE801FB04A') { throw 'Android command-line tools SHA256 mismatch.' }
if ((Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $downloadsRoot 'gradle8.13.zip')).Hash -ne '20F1B1176237254A6FC204D8434196FA11A4CFB387567519C61556E8710AED78') { throw 'Gradle SHA256 mismatch.' }
$jdkRoot = Join-Path $toolsRoot 'jdk17'
if (!(Test-Path -LiteralPath "$jdkRoot\bin\java.exe")) {
    $jdkUnpack = Join-Path $toolsRoot 'jdk-unpack'
    Expand-Archive -LiteralPath (Join-Path $downloadsRoot 'jdk17.zip') -DestinationPath $jdkUnpack
    $jdkFolder = @(Get-ChildItem -LiteralPath $jdkUnpack -Directory)
    if ($jdkFolder.Count -ne 1) { throw 'JDK archive must contain one directory.' }
    Move-Item -LiteralPath $jdkFolder[0].FullName -Destination $jdkRoot
}
$gradleRoot = Join-Path $toolsRoot 'gradle-8.13'
if (!(Test-Path -LiteralPath "$gradleRoot\bin\gradle.bat")) {
    Expand-Archive -LiteralPath (Join-Path $downloadsRoot 'gradle8.13.zip') -DestinationPath $toolsRoot
}
$sdkRoot = Join-Path $toolsRoot 'android-sdk'
$sdkManager = Join-Path $sdkRoot 'cmdline-tools\latest\bin\sdkmanager.bat'
if (!(Test-Path -LiteralPath $sdkManager)) {
    $sdkUnpack = Join-Path $toolsRoot 'sdk-unpack'
    Expand-Archive -LiteralPath $androidArchive -DestinationPath $sdkUnpack
    New-Item -ItemType Directory -Force -Path "$sdkRoot\cmdline-tools" | Out-Null
    Move-Item -LiteralPath "$sdkUnpack\cmdline-tools" -Destination "$sdkRoot\cmdline-tools\latest"
}
$env:JAVA_HOME = $jdkRoot
$env:ANDROID_HOME = $sdkRoot
$env:GRADLE_USER_HOME = Join-Path $projectRoot '.gradle'
# Accept the SDK licenses required for the user's authorized local Android build.
1..100 | ForEach-Object { 'y' } | & $sdkManager "--sdk_root=$sdkRoot" --licenses
if ($LASTEXITCODE -ne 0) { throw 'Android SDK license acceptance failed.' }
& $sdkManager "--sdk_root=$sdkRoot" 'platform-tools' 'platforms;android-35' 'build-tools;35.0.0'
if ($LASTEXITCODE -ne 0) { throw 'Android SDK package installation failed.' }
if (!(Test-Path -LiteralPath (Join-Path $projectRoot 'gradlew.bat'))) {
    $wrapperRoot = Join-Path $toolsRoot 'wrapper-bootstrap'
    New-Item -ItemType Directory -Force -Path $wrapperRoot | Out-Null
    [IO.File]::WriteAllText((Join-Path $wrapperRoot 'settings.gradle'), "rootProject.name = 'WrapperBootstrap'`n")
    & "$gradleRoot\bin\gradle.bat" -p $wrapperRoot wrapper --gradle-version 8.13 --distribution-type bin --console=plain
    if ($LASTEXITCODE -ne 0) { throw 'Gradle wrapper generation failed.' }
    Copy-Item -LiteralPath "$wrapperRoot\gradlew", "$wrapperRoot\gradlew.bat" -Destination $projectRoot
    Copy-Item -LiteralPath "$wrapperRoot\gradle" -Destination $projectRoot -Recurse
}
Write-Output 'Toolchain ready. Run tools/build.ps1.'
