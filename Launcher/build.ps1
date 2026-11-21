#requires -Version 5.1
param(
    [switch]$Sign,
    [string]$CertPath = $env:SLLK_SIGN_CERT,
    [string]$CertPassword = $env:SLLK_SIGN_PASSWORD,
    [string]$TimestampUrl = "http://timestamp.digicert.com"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$build = Join-Path $root "build"
$out = Join-Path $root "SllkGuiLauncher.exe"
New-Item -ItemType Directory -Force -Path $build | Out-Null

$csc = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-not (Test-Path $csc)) {
    $csc = Join-Path $env:WINDIR "Microsoft.NET\Framework\v4.0.30319\csc.exe"
}
if (-not (Test-Path $csc)) { throw "找不到 csc.exe（需要 .NET Framework 4.x）" }

$fw = Split-Path -Parent $csc
$refNames = @(
    "System.dll", "System.Core.dll", "System.Net.Http.dll",
    "System.IO.Compression.dll", "System.IO.Compression.FileSystem.dll",
    "System.Web.Extensions.dll", "System.Windows.Forms.dll",
    "System.Drawing.dll", "System.Security.dll"
)
$refs = @()
foreach ($name in $refNames) {
    $path = Join-Path $fw $name
    if (Test-Path $path) { $refs += "/reference:$path" }
}

Write-Host "压缩内嵌 UI ..."
$uiBytes = [IO.File]::ReadAllBytes((Join-Path $root "ui\index.html"))
$ms = New-Object IO.MemoryStream
$gz = New-Object IO.Compression.GZipStream($ms, [IO.Compression.CompressionMode]::Compress, $true)
$gz.Write($uiBytes, 0, $uiBytes.Length)
$gz.Close()
[IO.File]::WriteAllBytes((Join-Path $build "ui.html.gz"), $ms.ToArray())
$ms.Dispose()
Write-Host ("  ui {0:N0} B -> {1:N0} B" -f $uiBytes.Length, (Get-Item (Join-Path $build "ui.html.gz")).Length)

Write-Host "检查图标资源 ..."
$iconPath = Join-Path $root "icon.ico"
$svgPath = Join-Path $root "mihoutao.svg"
if (-not (Test-Path $iconPath)) { throw "缺少 icon.ico（exe 图标与 favicon）" }
if (-not (Test-Path $svgPath)) { throw "缺少 mihoutao.svg（界面品牌图标）" }

Write-Host "编译 ..."
$sources = @(Get-ChildItem (Join-Path $root "src") -Filter "*.cs" | ForEach-Object { $_.FullName })
$cscArgs = @(
    "/nologo", "/target:winexe", "/platform:anycpu", "/optimize+", "/debug-", "/langversion:5",
    "/out:$out",
    "/win32manifest:$(Join-Path $root 'app.manifest')",
    "/win32icon:$iconPath",
    "/resource:$(Join-Path $build 'ui.html.gz'),Launcher.Ui.index.html.gz",
    "/resource:$iconPath,Launcher.Ui.icon.ico",
    "/resource:$svgPath,Launcher.Ui.mihoutao.svg",
    "/resource:$(Join-Path $root 'manifest.json'),Launcher.manifest.json"
) + $refs + $sources

& $csc @cscArgs
if ($LASTEXITCODE -ne 0) { throw "编译失败，退出码 $LASTEXITCODE" }

$file = Get-Item $out
$vi = $file.VersionInfo
Write-Host ("输出 {0} · {1:N0} B · FileVersion {2} · Product {3}" -f $file.Name, $file.Length, $vi.FileVersion, $vi.ProductName)

if ($Sign) {
    if (-not $CertPath -or -not (Test-Path $CertPath)) {
        Write-Warning "已请求签名，但未提供有效证书（-CertPath 或 SLLK_SIGN_CERT）；输出仍未签名。"
    } else {
        $signtool = (Get-Command signtool.exe -ErrorAction SilentlyContinue).Source
        if (-not $signtool) {
            $kits = @(
                "${env:ProgramFiles(x86)}\Windows Kits\10\bin",
                "$env:ProgramFiles\Windows Kits\10\bin"
            )
            foreach ($kit in $kits) {
                if (-not (Test-Path $kit)) { continue }
                $found = Get-ChildItem $kit -Recurse -Filter signtool.exe -ErrorAction SilentlyContinue | Select-Object -First 1
                if ($found) { $signtool = $found.FullName; break }
            }
        }
        if (-not $signtool) { throw "找不到 signtool.exe" }
        $signArgs = @("sign", "/fd", "SHA256", "/f", $CertPath, "/tr", $TimestampUrl, "/td", "SHA256")
        if ($CertPassword) { $signArgs += @("/p", $CertPassword) }
        $signArgs += $out
        & $signtool @signArgs
        if ($LASTEXITCODE -ne 0) { throw "签名失败，退出码 $LASTEXITCODE" }
        Write-Host "签名完成。"
    }
} else {
    Write-Host "未签名构建。发布时请使用 -Sign -CertPath <pfx> 或设置 SLLK_SIGN_CERT。"
}
