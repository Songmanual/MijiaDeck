# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 MiHome-Windows contributors
<#
.SYNOPSIS
    MijiaDeck 一键构建脚本
.DESCRIPTION
    自动完成：venv 创建 → 依赖安装 → Nuitka 编译
    需要：Python 3.10+, VS Build Tools 2022
.EXAMPLE
    .\build.ps1
    .\build.ps1 -Clean
#>

param([switch]$Clean)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

# ============================================================
# 1. 自动创建 venv 并安装依赖
# ============================================================
$Pip = Join-Path $Root ".venv\Scripts\pip.exe"
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Pip)) {
    Write-Host "[1/3] Creating virtual environment..." -ForegroundColor Cyan

    # 尝试 py launcher，失败则用 python
    $PyCmd = Get-Command py -ErrorAction SilentlyContinue
    if ($PyCmd) {
        & py -3 -m venv (Join-Path $Root ".venv")
    } else {
        & python -m venv (Join-Path $Root ".venv")
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] 创建 venv 失败，请确认 Python 3 已安装并加入 PATH" -ForegroundColor Red
        exit 1
    }

    Write-Host "[2/3] Installing dependencies... (showing pip progress; a 'new version of pip' notice is informational only)" -ForegroundColor Cyan
    # 不用 --quiet：依赖下载可达数百 MB，静默会让人误以为卡死；
    # pip 的升级提示/进度条直接透传
    & $Python -m pip install -e $Root
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] 安装依赖失败" -ForegroundColor Red
        exit 1
    }

    Write-Host "[3/3] 初始化完成`n" -ForegroundColor Green
} else {
    Write-Host "[OK] Virtual environment ready" -ForegroundColor Green
}

# ============================================================
# 2. 激活 MSVC 编译环境
# ============================================================
$Vcvars = "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
if (-not (Test-Path $Vcvars)) {
    Write-Host "[ERROR] VS Build Tools 2022 not found" -ForegroundColor Red
    Write-Host "Download: https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022" -ForegroundColor Yellow
    exit 1
}

Write-Host "Activating MSVC environment..." -ForegroundColor Cyan

$MsvcEnv = cmd /c "`"$Vcvars`" >nul 2>&1 && set"
foreach ($Line in $MsvcEnv) {
    if ($Line -match '^([^=]+)=(.*)$') {
        [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], "Process")
    }
}
# vcvars 在部分机器上不导出该变量，缺失时兜底；已有值则尊重本机 SDK
if (-not $Env:WindowsSDKVersion -or $Env:WindowsSDKVersion -eq "0.0.0.0") {
    $Env:WindowsSDKVersion = "10.0.26100.0"
}
Write-Host "MSVC ready" -ForegroundColor Green

# ============================================================
# 3. 前置检查（Nuitka 缺失即补装，兼容先跑过 start.bat 的旧 venv）
# ============================================================
# 注意：探测必须经 cmd /c 在 cmd 层丢弃 stderr。脚本开头
# $ErrorActionPreference = "Stop" 时，PowerShell 会把带 2>$null 的
# 原生命令 stderr 转成终止性错误——全新 venv 没装 Nuitka，探测
# 必然失败，脚本会在「Installing Nuitka」分支之前直接死掉。

function Get-NuitkaVersion {
    $code = "from nuitka.Version import getNuitkaVersion; print(getNuitkaVersion())"
    $out = cmd /c "`"$Python`" -c `"$code`" 2>nul"
    if ($LASTEXITCODE -ne 0) {
        return $null
    }
    return ($out | Out-String).Trim()
}

$NuitkaVer = Get-NuitkaVersion
if (-not $NuitkaVer) {
    Write-Host "Installing Nuitka... (downloading compiler toolchain, may take a minute)" -ForegroundColor Cyan
    & $Python -m pip install nuitka ordered-set zstandard
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] 安装 Nuitka 失败" -ForegroundColor Red
        exit 1
    }
    $NuitkaVer = Get-NuitkaVersion
    if (-not $NuitkaVer) {
        Write-Host "[ERROR] Nuitka 未安装" -ForegroundColor Red
        exit 1
    }
}
Write-Host "Nuitka $NuitkaVer" -ForegroundColor Green

# ============================================================
# 4. 清理
# ============================================================
if ($Clean -and (Test-Path "dist")) {
    Remove-Item "dist" -Recurse -Force
}

# ============================================================
# 5. 构建
# ============================================================

$NuitkaArgs = @(
    "run.py"
    "--standalone"
    "--enable-plugin=pyside6"
    "--windows-console-mode=disable"
    "--windows-icon-from-ico=app\ui\icon.ico"
    "--include-package=app.siui"
    "--include-package=qtawesome"
    "--include-package-data=qtawesome"
    "--include-data-files=app\ui\icon.png=app/ui/icon.png"
    "--include-data-files=app\ui\icon.ico=app/ui/icon.ico"
    "--include-data-dir=app\ui\icons=app/ui/icons"
    "--include-data-files=app\ui\tray_icon.png=app/ui/tray_icon.png"
    "--include-data-files=app\ui\tray_icon_light.png=app/ui/tray_icon_light.png"
    "--nofollow-import-to=tkinter,unittest,pytest"
    "--noinclude-dlls=qt6datavisualization.dll"
    "--noinclude-dlls=qt6pdf.dll"
    "--jobs=4"
    "--assume-yes-for-downloads"
    "--output-dir=dist"
    "--output-filename=MijiaDeck.exe"
    # 版本号自动从 app/__init__.py 的 __version__ 读取，单一信源
    $AppVersion = (Select-String -Path "app\__init__.py" -Pattern '^__version__\s*=\s*"(.+?)"').Matches[0].Groups[1].Value
    Write-Host "  Version: $AppVersion" -ForegroundColor Gray
    "--product-name=MijiaDeck"
    "--product-version=$AppVersion"
    "--file-version=$AppVersion"
    "--copyright=Copyright (C) 2026 MiHome-Windows contributors"
)

Write-Host "`nBuilding MijiaDeck..." -ForegroundColor Cyan
Write-Host "(这是最耗时的一步，通常需要几分钟；期间会输出 Nuitka 各阶段进度，请勿关闭窗口)`n" -ForegroundColor Yellow
$BuildStart = Get-Date
& $Python -m nuitka @NuitkaArgs

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] 构建失败" -ForegroundColor Red
    exit 1
}
$Elapsed = (Get-Date) - $BuildStart
Write-Host ("`n编译耗时 {0:00}:{1:00}" -f [int]$Elapsed.TotalMinutes, $Elapsed.Seconds) -ForegroundColor Gray

# ============================================================
# 6. 整理输出
# ============================================================
if (Test-Path "dist\run.dist") {
    robocopy "dist\run.dist" "dist" /move /E /NFL /NDL /NJH /NJS /NC /NS /NP | Out-Null
    Remove-Item "dist\run.build" -Recurse -Force -ErrorAction SilentlyContinue
}

$Exe = "dist\MijiaDeck.exe"
if (Test-Path $Exe) {
    $Size = [math]::Round((Get-Item $Exe).Length / 1MB, 1)
    Write-Host "`n构建成功! $Exe ($Size MB)" -ForegroundColor Green
} else {
    Write-Host "[ERROR] 找不到输出文件" -ForegroundColor Red
}
