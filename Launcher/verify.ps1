#requires -Version 5.1
param(
    [switch]$RequireSignature
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$exe = Join-Path $root "SllkGuiLauncher.exe"

& (Join-Path $root "build.ps1")
if (-not (Test-Path $exe)) { throw "构建产物不存在：$exe" }

$file = Get-Item $exe
$vi = $file.VersionInfo
Write-Host ("EXE: {0:N0} B · FileVersion {1} · ProductVersion {2} · {3}" -f $file.Length, $vi.FileVersion, $vi.ProductVersion, $vi.ProductName)
if (-not $vi.FileVersion.StartsWith("5.0.0")) { throw "版本信息不符合预期：$($vi.FileVersion)" }
if ($file.Length -gt 1MB) { throw "exe 超过 1 MB：$($file.Length)" }

Write-Host "运行内建自检 ..."
$p = Start-Process -FilePath $exe -ArgumentList "--selftest" -Wait -PassThru -NoNewWindow
if ($p.ExitCode -ne 0) { throw "selftest 失败，退出码 $($p.ExitCode)" }

Write-Host "运行安装计划 ..."
$p2 = Start-Process -FilePath $exe -ArgumentList "--print-plan" -Wait -PassThru -NoNewWindow
if ($p2.ExitCode -ne 0) { throw "print-plan 失败，退出码 $($p2.ExitCode)" }

$sig = Get-AuthenticodeSignature -LiteralPath $exe
Write-Host "签名状态：$($sig.Status)"
if ($RequireSignature -and $sig.Status -ne "Valid") { throw "要求签名，但当前状态为 $($sig.Status)" }

Write-Host "VERIFY PASS"
