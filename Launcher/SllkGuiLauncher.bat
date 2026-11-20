@echo off
setlocal
set "SLLK_LAUNCHER=%~f0"
start "" powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "try { $t=[IO.File]::ReadAllText($env:SLLK_LAUNCHER,[Text.Encoding]::UTF8); $m=('#__SLLK_' + 'BODY__'); $i=$t.LastIndexOf($m); if($i -lt 0){ throw 'launcher body not found' }; iex $t.Substring($i+$m.Length) } catch { Add-Type -AssemblyName System.Windows.Forms; [Windows.Forms.MessageBox]::Show(($_.Exception.Message + [Environment]::NewLine + $_.InvocationInfo.PositionMessage),'SllkGui Launcher','OK','Error') | Out-Null }"
exit /b 0
#__SLLK_BODY__

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

# ---------------------------------------------------------------------------
# 启动器根目录 / 运行时目录（启动器私有，与基座代码完全解耦）
# ---------------------------------------------------------------------------
$LauncherFile = $env:SLLK_LAUNCHER
if(-not $LauncherFile -or -not (Test-Path -LiteralPath $LauncherFile)){ throw '启动器路径丢失，请通过 SllkGuiLauncher.bat 启动。' }
$Root = Split-Path -Parent $LauncherFile
$Runtime = Join-Path $Root 'runtime'
$Writable = $true
try {
  if(-not (Test-Path -LiteralPath $Runtime)){ New-Item -ItemType Directory -Force -Path $Runtime | Out-Null }
  $probe = Join-Path $Runtime '.probe'
  [IO.File]::WriteAllText($probe,'1')
  Remove-Item -LiteralPath $probe -Force
} catch { $Writable = $false }
if(-not $Writable){
  $Runtime = Join-Path $env:LOCALAPPDATA 'SllkGuiLauncher'
  if(-not (Test-Path -LiteralPath $Runtime)){ New-Item -ItemType Directory -Force -Path $Runtime | Out-Null }
}
$BaseDir = Join-Path $Runtime 'base'
$LogDir = Join-Path $Runtime 'logs'
$CacheDir = Join-Path $Runtime 'cache'
foreach($d in @($LogDir,$CacheDir)){
  if(-not (Test-Path -LiteralPath $d)){ New-Item -ItemType Directory -Force -Path $d | Out-Null }
}

# ---------------------------------------------------------------------------
# 配置（镜像源持久化）
# ---------------------------------------------------------------------------
$ConfigPath = Join-Path $Runtime 'config.json'
$Config = @{ mirror = 'cn'; repo = 'https://gitee.com/shilianlvke/SllkGui.git'; branch = 'main'; python = '3.12'; mode = 'run' }
if(Test-Path -LiteralPath $ConfigPath){
  try {
    $saved = Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach($k in @('mirror','repo','branch','python','mode')){
      if($saved.PSObject.Properties.Name -contains $k){
        $v = [string]$saved.$k
        if($v){ $Config[$k] = $v }
      }
    }
  } catch { }
}
function Save-Config {
  try { $Config | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $ConfigPath -Encoding UTF8 } catch { }
}

function Get-MirrorProfile([string]$mode){
  if($mode -eq 'global'){
    return [pscustomobject]@{
      mode = 'global'
      label = '官方源'
      pypi = 'https://pypi.org/simple'
      gh = 'https://github.com'
      api = 'https://api.github.com'
      py = 'https://github.com/astral-sh/python-build-standalone/releases/download'
      uvFallback = '0.13.8'
    }
  }
  return [pscustomobject]@{
    mode = 'cn'
    label = '国内镜像'
    pypi = 'https://pypi.tuna.tsinghua.edu.cn/simple'
    gh = 'https://gh-proxy.com/https://github.com'
    api = 'https://gh-proxy.com/https://api.github.com'
    py = 'https://gh-proxy.com/https://github.com/astral-sh/python-build-standalone/releases/download'
    uvFallback = '0.13.8'
  }
}

# ---------------------------------------------------------------------------
# 单实例锁（按启动器所在目录隔离，不同副本互不影响）
# ---------------------------------------------------------------------------
$OwnerKey = ([BitConverter]::ToString([System.Security.Cryptography.MD5]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes($Root.ToLowerInvariant())))).Replace('-','').Substring(0,12)
$Mutex = [System.Threading.Mutex]::new($false, 'Local\SllkGuiLauncher.' + $OwnerKey)
$IsPrimary = $Mutex.WaitOne(0)

# ---------------------------------------------------------------------------
# 工具定位
# ---------------------------------------------------------------------------
$UvLocal = Join-Path $Runtime 'tools\uv\uv.exe'
$GitLocal = Join-Path $Runtime 'tools\git\cmd\git.exe'
function Add-PathEntry([string]$dir){
  if(-not $dir -or -not (Test-Path -LiteralPath $dir)){ return }
  $parts = $env:Path -split ';'
  if($parts -notcontains $dir){ $env:Path = $dir + ';' + $env:Path }
}
Add-PathEntry (Split-Path -Parent $UvLocal)
Add-PathEntry (Split-Path -Parent $GitLocal)

function Resolve-Tool([string]$name,[string]$preferred){
  if($preferred -and (Test-Path -LiteralPath $preferred)){ return $preferred }
  $cmd = Get-Command $name -ErrorAction SilentlyContinue | Where-Object { $_.CommandType -eq 'Application' } | Select-Object -First 1
  if($cmd){ return $cmd.Source }
  return $null
}

# ---------------------------------------------------------------------------
# 环境检测
# ---------------------------------------------------------------------------
$script:StateCache = $null
$script:StateCacheAt = [DateTime]::MinValue

function Get-EnvironmentState {
  $uv = Resolve-Tool 'uv' $UvLocal
  $gitExe = Resolve-Tool 'git' $GitLocal
  $uvVer = ''; $gitVer = ''; $pyPath = ''; $pyVer = ''
  if($uv){ try { $uvVer = ([string]((& $uv --version 2>$null) | Select-Object -First 1)).Trim() } catch { } }
  if($gitExe){ try { $gitVer = ([string]((& $gitExe --version 2>$null) | Select-Object -First 1)).Trim() } catch { } }
  if($uv){
    try {
      $found = & $uv python find $Config.python --managed-python 2>$null
      if($found){
        $cand = ([string]($found | Select-Object -Last 1)).Trim()
        if($cand -and (Test-Path -LiteralPath $cand)){ $pyPath = $cand }
      }
    } catch { }
  }
  if($pyPath){ try { $pyVer = ([string]((& $pyPath --version 2>$null) | Select-Object -First 1)).Trim() } catch { } }
  $repoOk = Test-Path -LiteralPath (Join-Path $BaseDir '.git\HEAD')
  $venvPy = Join-Path $BaseDir '.venv\Scripts\python.exe'
  $venvOk = Test-Path -LiteralPath $venvPy
  $depsOk = $false
  if($venvOk){
    $site = Join-Path $BaseDir '.venv\Lib\site-packages'
    $entryExe = Join-Path $BaseDir '.venv\Scripts\sllkgui.exe'
    if((Test-Path -LiteralPath $site) -and (Test-Path -LiteralPath $entryExe)){
      try {
        $n = @(Get-ChildItem -LiteralPath $site -Directory -ErrorAction SilentlyContinue).Count
        if($n -ge 3){ $depsOk = $true }
      } catch { }
    }
  }
  $ready = [bool]($uv -and $pyPath -and $gitExe -and $repoOk -and $venvOk -and $depsOk)
  return [pscustomobject]@{
    uv = $uv; uvVersion = $uvVer
    python = $pyPath; pythonVersion = $pyVer
    git = $gitExe; gitVersion = $gitVer
    repo = $repoOk; venv = $venvOk; deps = $depsOk
    ready = $ready
  }
}

function Get-State([bool]$Force){
  if(-not $Force -and $script:StateCache -and ((Get-Date) - $script:StateCacheAt).TotalSeconds -lt 3){
    return $script:StateCache
  }
  $script:StateCache = Get-EnvironmentState
  $script:StateCacheAt = Get-Date
  return $script:StateCache
}

# ---------------------------------------------------------------------------
# 共享状态
# ---------------------------------------------------------------------------
$Shared = [hashtable]::Synchronized(@{ phase = 'idle'; error = ''; current = ''; updateRef = ''; startedAt = $null; finishedAt = $null; cancel = $false })
$Steps = [hashtable]::Synchronized(@{})
$Queue = [System.Collections.Concurrent.ConcurrentQueue[object]]::new()
$LogLines = [System.Collections.ArrayList]::new()
$script:LogDropped = 0
$script:Clients = @{}
$script:Token = [guid]::NewGuid().ToString('N')
$script:Shutdown = $false
$script:ByeAt = $null
$script:ExitReason = 'unknown'
$script:Pipeline = $null
$script:Runspace = $null
$script:Handle = $null
$script:AppProcess = $null

$StepDefs = @(
  @{ id = 'uv';     label = 'uv 包管理器'; short = 'uv';       hint = 'uv.exe' },
  @{ id = 'python'; label = 'CPython 解释器'; short = 'cpython'; hint = 'cpython 3.12' },
  @{ id = 'git';    label = 'Git 客户端';   short = 'git';     hint = 'git' },
  @{ id = 'repo';   label = '基座源码';     short = 'source';  hint = 'git clone' },
  @{ id = 'venv';   label = '虚拟环境';     short = 'venv';    hint = 'uv venv' },
  @{ id = 'deps';   label = '依赖同步';     short = 'deps';    hint = 'uv sync' }
)

$script:AppPidCache = 0
$script:AppOwnedCache = $false
$script:AppPidChecked = [DateTime]::MinValue

function Get-BaseProcess {
  $result = [pscustomobject]@{ pid = 0; owned = $false }
  if($script:AppProcess){
    try {
      $script:AppProcess.Refresh()
      if(-not $script:AppProcess.HasExited){
        $result.pid = [int]$script:AppProcess.Id
        $result.owned = $true
        return $result
      }
    } catch { }
  }
  if(((Get-Date) - $script:AppPidChecked).TotalSeconds -lt 3){
    $result.pid = $script:AppPidCache
    $result.owned = $script:AppOwnedCache
    return $result
  }
  $script:AppPidChecked = Get-Date
  $script:AppPidCache = 0
  $script:AppOwnedCache = $false
  try {
    $needle = (Join-Path $BaseDir '.venv\Scripts\sllkgui.exe').ToLower()
    $procs = Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe' OR Name = 'sllkgui.exe'" -ErrorAction SilentlyContinue
    foreach($p in $procs){
      $cl = [string]$p.CommandLine
      if(-not $cl){ continue }
      $low = $cl.ToLower()
      if($low.Contains($needle)){
        $script:AppPidCache = [int]$p.ProcessId
        $script:AppOwnedCache = $true
        break
      }
      if($script:AppPidCache -eq 0 -and $low -match 'sllkgui(\.exe)?["\s].*\b(run|gallery)\b'){
        $script:AppPidCache = [int]$p.ProcessId
      }
    }
  } catch { }
  $result.pid = $script:AppPidCache
  $result.owned = $script:AppOwnedCache
  return $result
}

function Get-BaseProcessId { return (Get-BaseProcess).pid }

function Test-AppRunning {
  return ((Get-BaseProcess).pid -gt 0)
}

function Build-Steps($envState){
  $map = @{}
  foreach($k in @($Steps.Keys)){ $map[$k] = $Steps[$k] }
  $running = Test-AppRunning
  $list = New-Object System.Collections.ArrayList
  foreach($d in $StepDefs){
    $state = 'wait'
    $note = $d.hint
    if($map.ContainsKey($d.id)){
      $state = [string]$map[$d.id].state
      $note = [string]$map[$d.id].note
    } else {
      if($d.id -eq 'uv' -and $envState.uv){ $state = 'ok'; $note = $envState.uvVersion }
      if($d.id -eq 'python' -and $envState.python){ $state = 'ok'; $note = $envState.pythonVersion }
      if($d.id -eq 'git' -and $envState.git){ $state = 'ok'; $note = $envState.gitVersion }
      if($d.id -eq 'repo' -and $envState.repo){ $state = 'ok'; $note = '已拉取' }
      if($d.id -eq 'venv' -and $envState.venv){ $state = 'ok'; $note = '已创建' }
      if($d.id -eq 'deps' -and $envState.deps){ $state = 'ok'; $note = '已同步' }
    }
    [void]$list.Add([pscustomobject]@{
      id = $d.id; label = $d.label; short = $d.short; hint = $d.hint; state = $state; note = $note
    })
  }
  return $list
}

# ---------------------------------------------------------------------------
# 版本检测：本地 HEAD 与远端 tag / main 的差异（只读 ls-remote，不改本地仓库）
# ---------------------------------------------------------------------------
$script:VersionCache = $null
$script:VersionCacheAt = [DateTime]::MinValue
$script:LocalHead = ''
$script:LocalHeadAt = [DateTime]::MinValue

function Get-RefVersionKey([string]$name){
  $parts = @(0,0,0,0)
  $i = 0
  foreach($m in [regex]::Matches($name, '\d+')){
    if($i -ge 4){ break }
    $parts[$i] = [int]$m.Value
    $i = $i + 1
  }
  return ('{0:D4}.{1:D4}.{2:D4}.{3:D4}' -f $parts[0], $parts[1], $parts[2], $parts[3])
}

function Invoke-Git {
  param([string[]]$ArgList)
  $git = Resolve-Tool 'git' $GitLocal
  if(-not $git){ return [pscustomobject]@{ ok = $false; code = -1; out = @(); error = '未找到 git' } }
  $prev = $ErrorActionPreference
  $out = @()
  $code = -1
  try {
    $env:GIT_TERMINAL_PROMPT = '0'
    $ErrorActionPreference = 'Continue'
    $out = @(& $git @ArgList 2>&1 | ForEach-Object { ([string]$_).TrimEnd() })
    $code = $LASTEXITCODE
  } catch {
    return [pscustomobject]@{ ok = $false; code = -1; out = @(); error = $_.Exception.Message }
  } finally {
    $ErrorActionPreference = $prev
  }
  return [pscustomobject]@{ ok = ($code -eq 0); code = $code; out = $out; error = '' }
}

function Get-LocalHead {
  if(-not (Test-Path -LiteralPath (Join-Path $BaseDir '.git'))){ return '' }
  if($script:LocalHead -and ((Get-Date) - $script:LocalHeadAt).TotalSeconds -lt 5){ return $script:LocalHead }
  $r = Invoke-Git @('-C', $BaseDir, 'rev-parse', 'HEAD')
  $script:LocalHead = ''
  if($r.ok -and @($r.out).Count -gt 0){ $script:LocalHead = ([string]$r.out[0]).Trim() }
  $script:LocalHeadAt = Get-Date
  return $script:LocalHead
}

function Get-RemoteVersions([bool]$Force){
  if(-not $Force -and $script:VersionCache -and ((Get-Date) - $script:VersionCacheAt).TotalSeconds -lt 120){
    return $script:VersionCache
  }
  $result = [pscustomobject]@{ ok = $false; error = ''; tags = @(); mainSha = ''; baseLatest = $null }
  if(-not (Test-Path -LiteralPath (Join-Path $BaseDir '.git'))){
    $result.error = '尚未拉取源码'
    $script:VersionCache = $null
    $script:VersionCacheAt = [DateTime]::MinValue
    return $result
  }
  $r = Invoke-Git @('-c','http.lowSpeedLimit=1000','-c','http.lowSpeedTime=15','ls-remote','--tags','--heads',$Config.repo)
  if(-not $r.ok){
    $msg = ''
    foreach($line in $r.out){ if($line){ $msg = $line } }
    if(-not $msg){ $msg = $r.error }
    $result.error = '无法读取远端版本'
    if($msg){ $result.error = $result.error + '：' + $msg }
    $script:VersionCache = $null
    $script:VersionCacheAt = [DateTime]::MinValue
    return $result
  }
  $map = @{}
  $mainSha = ''
  foreach($line in $r.out){
    if($line -notmatch '^([0-9a-f]{40})\s+(\S+)$'){ continue }
    $sha = $Matches[1]
    $ref = $Matches[2]
    if($ref -eq 'refs/heads/main'){ $mainSha = $sha; continue }
    if($ref -notlike 'refs/tags/*'){ continue }
    if($ref.EndsWith('^{}')){
      $name = $ref.Substring(10, $ref.Length - 13)
      $map[$name] = $sha
    } else {
      $name = $ref.Substring(10)
      if(-not $map.ContainsKey($name)){ $map[$name] = $sha }
    }
  }
  $tags = @()
  foreach($name in @($map.Keys)){
    $tags += [pscustomobject]@{
      name = [string]$name
      sha = [string]$map[$name]
      key = (Get-RefVersionKey ([string]$name))
    }
  }
  $tags = @($tags | Sort-Object -Property key -Descending)
  $baseLatest = $null
  foreach($t in $tags){
    if($t.name -match '^base-'){ $baseLatest = $t; break }
  }
  if(-not $baseLatest -and @($tags).Count -gt 0){ $baseLatest = $tags[0] }
  $result.ok = $true
  $result.tags = $tags
  $result.mainSha = $mainSha
  $result.baseLatest = $baseLatest
  $script:VersionCache = $result
  $script:VersionCacheAt = Get-Date
  return $result
}

function Read-RefRecord {
  $path = Join-Path $Runtime 'base-ref.json'
  if(-not (Test-Path -LiteralPath $path)){ return $null }
  try { return (Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json) } catch { return $null }
}

function Save-RefRecord([string]$ref,[string]$sha){
  if(-not $sha){ return }
  try {
    $obj = [pscustomobject]@{ ref = $ref; sha = $sha; at = (Get-Date).ToString('s') }
    [IO.File]::WriteAllText((Join-Path $Runtime 'base-ref.json'), ($obj | ConvertTo-Json -Compress), (New-Object System.Text.UTF8Encoding($false)))
  } catch { }
}

function Get-VersionState([bool]$Refresh,[bool]$CacheOnly){
  $localSha = Get-LocalHead
  if($CacheOnly -and -not $script:VersionCache){
    $remote = [pscustomobject]@{ ok = $false; error = ''; tags = @(); mainSha = ''; baseLatest = $null }
  } else {
    $remote = Get-RemoteVersions $Refresh
  }
  $currentRef = ''
  if($localSha){
    $rec = Read-RefRecord
    if($rec -and ([string]$rec.sha) -eq $localSha -and $rec.ref){ $currentRef = [string]$rec.ref }
    if(-not $currentRef -and $remote.ok){
      foreach($t in @($remote.tags)){
        if($t.sha -eq $localSha){ $currentRef = $t.name; break }
      }
      if(-not $currentRef -and $remote.mainSha -eq $localSha){ $currentRef = 'main' }
    }
  }
  $latest = $null
  if($remote.ok -and $remote.baseLatest){ $latest = $remote.baseLatest }
  $updateAvailable = $false
  if($localSha -and $latest -and $currentRef -ne 'main' -and $localSha -ne $latest.sha){
    $updateAvailable = $true
  }
  $versions = @()
  if($remote.ok){
    $versions += [pscustomobject]@{
      ref = 'main'; label = 'main'; kind = 'branch'; dev = $true
      sha = [string]$remote.mainSha
      short = $(if($remote.mainSha){ $remote.mainSha.Substring(0, 7) } else { '' })
      latest = $false
      current = [bool]($localSha -and $localSha -eq $remote.mainSha)
    }
    foreach($t in @($remote.tags)){
      $versions += [pscustomobject]@{
        ref = $t.name; label = $t.name; kind = 'tag'; dev = $false
        sha = $t.sha
        short = $t.sha.Substring(0, 7)
        latest = [bool]($latest -and $t.name -eq $latest.name)
        current = [bool]($localSha -and $localSha -eq $t.sha)
      }
    }
  }
  return [pscustomobject]@{
    current = $currentRef
    sha = $localSha
    short = $(if($localSha){ $localSha.Substring(0, 7) } else { '' })
    latest = $(if($latest){ $latest.name } else { '' })
    latestSha = $(if($latest){ $latest.sha } else { '' })
    updateAvailable = $updateAvailable
    error = [string]$remote.error
    versions = @($versions)
  }
}

function Build-State {
  $envState = Get-State
  $steps = Build-Steps $envState
  $baseProc = Get-BaseProcess
  $running = ($baseProc.pid -gt 0)
  $phase = [string]$Shared.phase
  if($running){ $phase = 'running' }
  elseif($phase -eq 'idle' -and $envState.ready){ $phase = 'done' }
  $elapsed = 0
  if($Shared.startedAt -is [DateTime]){
    $end = Get-Date
    if($Shared.finishedAt -is [DateTime]){ $end = $Shared.finishedAt }
    $elapsed = [int]($end - $Shared.startedAt).TotalSeconds
    if($elapsed -lt 0){ $elapsed = 0 }
  }
  $done = 0
  foreach($s in $steps){ if($s.state -eq 'ok'){ $done = $done + 1 } }
  $mirrorLabel = '国内镜像'
  if($Config.mirror -eq 'global'){ $mirrorLabel = '官方源' }
  $mode = [string]$Config.mode
  if($mode -ne 'gallery'){ $mode = 'run' }
  $modeLabel = '正式模式'
  if($mode -eq 'gallery'){ $modeLabel = '预览模式' }
  $appPid = $baseProc.pid
  $ver = Get-VersionState $false $true
  return [pscustomobject]@{
    phase = $phase
    ready = [bool]$envState.ready
    mirror = [string]$Config.mirror
    mirrorLabel = $mirrorLabel
    mode = $mode
    modeLabel = $modeLabel
    progress = $done
    total = @($StepDefs).Count
    current = [string]$Shared.current
    elapsed = $elapsed
    error = [string]$Shared.error
    running = $running
    pid = $appPid
    owned = [bool]$baseProc.owned
    steps = @($steps)
    paths = [pscustomobject]@{ base = $BaseDir; runtime = $Runtime; logs = $LogDir }
    repo = [string]$Config.repo
    python = [string]$Config.python
    port = $script:Port
    version = [pscustomobject]@{
      ref = [string]$ver.current
      sha = [string]$ver.short
      latest = [string]$ver.latest
      updateAvailable = [bool]$ver.updateAvailable
    }
    update = [pscustomobject]@{
      active = [bool]($Shared.phase -eq 'update')
      ref = [string]$Shared.updateRef
    }
  }
}

# ---------------------------------------------------------------------------
# 后台安装管线（在独立 runspace 中执行，避免阻塞本地服务）
# ---------------------------------------------------------------------------
$PipelineScript = {
  $ctx = $args[0]
  $ErrorActionPreference = 'Stop'
  try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch { }
  try { Add-Type -AssemblyName System.IO.Compression.FileSystem | Out-Null } catch { }

  $shared = $ctx.Shared
  $steps = $ctx.Steps
  $queue = $ctx.Queue
  $runtime = $ctx.Runtime
  $base = $ctx.Base
  $cache = $ctx.Cache
  $mirror = $ctx.Mirror
  $pyWant = $ctx.PythonVersion

  function Write-Log([string]$level,[string]$text){
    $queue.Enqueue([pscustomobject]@{ t = (Get-Date).ToString('HH:mm:ss'); level = $level; text = $text })
  }
  function Set-Step([string]$id,[string]$state,[string]$note){
    if($shared.cancel){ throw '已取消初始化' }
    $steps[$id] = [pscustomobject]@{ state = $state; note = $note }
    if($state -eq 'active'){ $shared.current = $id }
  }
  function Get-RemoteFile([string]$url,[string]$dest){
    Write-Log 'net' ('下载 ' + $url)
    $dir = Split-Path -Parent $dest
    if(-not (Test-Path -LiteralPath $dir)){ New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    for($i = 1; $i -le 3; $i++){
      try {
        $wc = New-Object System.Net.WebClient
        try { $wc.Headers.Add('User-Agent','SllkGuiLauncher/1.0') } catch { }
        $wc.DownloadFile($url,$dest)
        $wc.Dispose()
        $len = 0
        try { $len = (Get-Item -LiteralPath $dest).Length } catch { }
        if($len -le 0){ throw '下载内容为空' }
        Write-Log 'ok' ('已下载 ' + [math]::Round($len / 1MB, 1) + ' MB')
        return
      } catch {
        if($i -ge 3){ throw }
        Write-Log 'warn' ('下载失败，重试 ' + $i + '/3：' + $_.Exception.Message)
        Start-Sleep -Seconds 2
      }
    }
  }
  function Expand-Zip([string]$zip,[string]$dest){
    if(Test-Path -LiteralPath $dest){ Remove-Item -LiteralPath $dest -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    [IO.Compression.ZipFile]::ExtractToDirectory($zip,$dest)
  }
  function Invoke-Native([string]$exe,[object[]]$argv){
    $shown = $exe + ' ' + (($argv | ForEach-Object { [string]$_ }) -join ' ')
    Write-Log 'cmd' $shown
    $code = 0
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
      & $exe @argv 2>&1 | ForEach-Object {
        $line = ([string]$_).TrimEnd()
        if($line.Length -gt 0){ Write-Log 'out' $line }
      }
      $code = $LASTEXITCODE
    } finally {
      $ErrorActionPreference = $prev
    }
    if($code -ne 0){ throw ('命令失败（退出码 ' + $code + '）：' + $shown) }
  }

  try {
    $shared.phase = 'setup'
    $shared.error = ''
    $uv = $ctx.UvPath
    $git = $ctx.GitPath

    # 1. uv -----------------------------------------------------------------
    Set-Step 'uv' 'active' '检测中'
    if(-not (Test-Path -LiteralPath $uv)){
      $c = Get-Command uv -ErrorAction SilentlyContinue | Where-Object { $_.CommandType -eq 'Application' } | Select-Object -First 1
      if($c){ $uv = $c.Source }
    }
    if(-not $uv -or -not (Test-Path -LiteralPath $uv)){
      Write-Log 'sys' '未检测到 uv，开始安装（不使用 pip）'
      $arch = 'x86_64'
      if($env:PROCESSOR_ARCHITECTURE -eq 'ARM64'){ $arch = 'aarch64' }
      $tag = $mirror.uvFallback
      try {
        $rel = Invoke-RestMethod -Uri ($mirror.api + '/repos/astral-sh/uv/releases/latest') -Headers @{ 'User-Agent' = 'SllkGuiLauncher/1.0' } -TimeoutSec 25
        if($rel.tag_name){ $tag = [string]$rel.tag_name }
      } catch { Write-Log 'warn' ('无法查询 uv 版本，使用内置版本 ' + $tag) }
      $url = $mirror.gh + '/astral-sh/uv/releases/download/' + $tag + '/uv-' + $arch + '-pc-windows-msvc.zip'
      $zip = Join-Path $cache 'uv.zip'
      Get-RemoteFile $url $zip
      Expand-Zip $zip (Join-Path $runtime 'tools\uv')
      $uv = Join-Path $runtime 'tools\uv\uv.exe'
      if(-not (Test-Path -LiteralPath $uv)){ throw 'uv 安装失败：未找到 uv.exe' }
    }
    $uvVer = ''
    try { $uvVer = ([string]((& $uv --version 2>$null) | Select-Object -First 1)).Trim() } catch { }
    Set-Step 'uv' 'ok' $uvVer
    Write-Log 'ok' ('uv 就绪 · ' + $uvVer)
    $env:Path = (Split-Path -Parent $uv) + ';' + $env:Path

    # 2. CPython ------------------------------------------------------------
    Set-Step 'python' 'active' '安装中'
    $pyPath = ''
    try {
      $found = & $uv python find $pyWant --managed-python 2>$null
      if($found){ $pyPath = ([string]($found | Select-Object -Last 1)).Trim() }
    } catch { }
    if($pyPath){
      Write-Log 'ok' ('CPython 已存在 · ' + $pyPath)
    } else {
      Write-Log 'sys' ('准备 CPython ' + $pyWant)
      $pyArgs = New-Object System.Collections.ArrayList
      [void]$pyArgs.Add('python'); [void]$pyArgs.Add('install'); [void]$pyArgs.Add($pyWant)
      [void]$pyArgs.Add('--no-bin'); [void]$pyArgs.Add('--no-registry')
      if($mirror.py){ [void]$pyArgs.Add('--mirror'); [void]$pyArgs.Add($mirror.py) }
      Invoke-Native $uv $pyArgs.ToArray()
      try {
        $found = & $uv python find $pyWant --managed-python 2>$null
        if($found){ $pyPath = ([string]($found | Select-Object -Last 1)).Trim() }
      } catch { }
    }
    if(-not $pyPath){ throw 'CPython 安装完成但无法定位解释器' }
    $pyVer = ''
    try { $pyVer = ([string]((& $pyPath --version 2>$null) | Select-Object -First 1)).Trim() } catch { }
    Set-Step 'python' 'ok' $pyVer
    Write-Log 'ok' ('CPython 就绪 · ' + $pyVer)

    # 3. Git ----------------------------------------------------------------
    Set-Step 'git' 'active' '检测中'
    if(-not (Test-Path -LiteralPath $git)){
      $c = Get-Command git -ErrorAction SilentlyContinue | Where-Object { $_.CommandType -eq 'Application' } | Select-Object -First 1
      if($c){ $git = $c.Source }
    }
    if(-not $git -or -not (Test-Path -LiteralPath $git)){
      Write-Log 'sys' '未检测到 Git，下载便携版 MinGit（免管理员权限）'
      $url = ''
      if($ctx.MirrorMode -eq 'cn'){
        try {
          $list = Invoke-RestMethod -Uri 'https://registry.npmmirror.com/-/binary/git-for-windows/' -TimeoutSec 25
          $ver = @($list | Where-Object { $_.name -match '^v\d+\.\d+\.\d+\.windows\.\d+/$' } | Select-Object -Last 1)
          if($ver.Count -gt 0){
            $verName = [string]$ver[0].name
            $files = Invoke-RestMethod -Uri ('https://registry.npmmirror.com/-/binary/git-for-windows/' + $verName) -TimeoutSec 25
            $asset = @($files | Where-Object { $_.name -match '^MinGit-.*-64-bit\.zip$' } | Select-Object -First 1)
            if($asset.Count -gt 0){ $url = 'https://registry.npmmirror.com/-/binary/git-for-windows/' + $verName + [string]$asset[0].name }
          }
        } catch { Write-Log 'warn' ('镜像站解析失败：' + $_.Exception.Message) }
      } else {
        try {
          $rel = Invoke-RestMethod -Uri ($mirror.api + '/repos/git-for-windows/git/releases/latest') -Headers @{ 'User-Agent' = 'SllkGuiLauncher/1.0' } -TimeoutSec 25
          $asset = @($rel.assets | Where-Object { $_.name -match '^MinGit-.*-64-bit\.zip$' } | Select-Object -First 1)
          if($asset.Count -gt 0){ $url = [string]$asset[0].browser_download_url }
        } catch { Write-Log 'warn' ('GitHub 解析失败：' + $_.Exception.Message) }
      }
      if(-not $url){
        $url = $mirror.gh + '/git-for-windows/git/releases/download/v2.47.1.windows.1/MinGit-2.47.1-64-bit.zip'
        Write-Log 'warn' '使用内置 MinGit 版本回退'
      }
      $zip = Join-Path $cache 'mingit.zip'
      Get-RemoteFile $url $zip
      Expand-Zip $zip (Join-Path $runtime 'tools\git')
      $git = Join-Path $runtime 'tools\git\cmd\git.exe'
      if(-not (Test-Path -LiteralPath $git)){ throw 'Git 安装失败：未找到 git.exe' }
    }
    $gitVer = ''
    try { $gitVer = ([string]((& $git --version 2>$null) | Select-Object -First 1)).Trim() } catch { }
    Set-Step 'git' 'ok' $gitVer
    Write-Log 'ok' ('Git 就绪 · ' + $gitVer)
    $env:Path = (Split-Path -Parent $git) + ';' + $env:Path

    # 4. 源码 ---------------------------------------------------------------
    Set-Step 'repo' 'active' '拉取中'
    $cloneRef = $ctx.Branch
    $cloned = $false
    if(-not (Test-Path -LiteralPath (Join-Path $base '.git'))){
      if(Test-Path -LiteralPath $base){ Remove-Item -LiteralPath $base -Recurse -Force }
      $parent = Split-Path -Parent $base
      if(-not (Test-Path -LiteralPath $parent)){ New-Item -ItemType Directory -Force -Path $parent | Out-Null }
      $env:GIT_TERMINAL_PROMPT = '0'
      # 默认拉取最新的 base-* 版本；探测失败时回落到分支
      $bestTag = ''
      $bestKey = ''
      $prev = $ErrorActionPreference
      $ErrorActionPreference = 'Continue'
      try {
        $ls = @(& $git -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=15 ls-remote --tags --heads $ctx.RepoUrl 2>&1 | ForEach-Object { [string]$_ })
      } catch {
        $ls = @()
      } finally {
        $ErrorActionPreference = $prev
      }
      $tagMap = @{}
      foreach($line in $ls){
        if($line -notmatch '^([0-9a-f]{40})\s+(\S+)$'){ continue }
        if($Matches[2] -notlike 'refs/tags/*'){ continue }
        if($Matches[2].EndsWith('^{}')){
          $tagMap[$Matches[2].Substring(10, $Matches[2].Length - 13)] = $Matches[1]
        } else {
          $n = $Matches[2].Substring(10)
          if(-not $tagMap.ContainsKey($n)){ $tagMap[$n] = $Matches[1] }
        }
      }
      foreach($n in @($tagMap.Keys)){
        if($n -notmatch '^base-'){ continue }
        $parts = @(0,0,0,0)
        $i = 0
        foreach($m in [regex]::Matches($n, '\d+')){
          if($i -ge 4){ break }
          $parts[$i] = [int]$m.Value
          $i = $i + 1
        }
        $k = ('{0:D4}.{1:D4}.{2:D4}.{3:D4}' -f $parts[0], $parts[1], $parts[2], $parts[3])
        if($k -gt $bestKey){ $bestKey = $k; $bestTag = $n }
      }
      if($bestTag){
        $cloneRef = $bestTag
        Write-Log 'sys' ('目标版本 ' + $bestTag + '（最新 base）')
      } else {
        Write-Log 'warn' '未找到 base-* 版本，回落到分支 ' + $ctx.Branch
      }
      Write-Log 'sys' ('克隆 ' + $ctx.RepoUrl + ' · ' + $cloneRef)
      Invoke-Native $git @('clone','--depth','1','--branch',$cloneRef,$ctx.RepoUrl,$base)
      $cloned = $true
    } else {
      Write-Log 'ok' '源码目录已存在，跳过克隆'
    }
    $headSha = ''
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { $headSha = ([string]((& $git -C $base rev-parse HEAD 2>$null) | Select-Object -First 1)).Trim() } finally { $ErrorActionPreference = $prev }
    if($headSha){
      $recPath = Join-Path $ctx.Runtime 'base-ref.json'
      $keep = $false
      if(Test-Path -LiteralPath $recPath){
        try {
          $rec = Get-Content -LiteralPath $recPath -Raw -Encoding UTF8 | ConvertFrom-Json
          if([string]$rec.sha -eq $headSha){ $keep = $true }
        } catch { }
      }
      if(-not $keep -and $cloned){
        $recObj = [pscustomobject]@{ ref = $cloneRef; sha = $headSha; at = (Get-Date).ToString('s') }
        [IO.File]::WriteAllText($recPath, ($recObj | ConvertTo-Json -Compress), (New-Object System.Text.UTF8Encoding($false)))
      }
    }
    Set-Step 'repo' 'ok' '已拉取'

    # 5. 虚拟环境 -----------------------------------------------------------
    Set-Step 'venv' 'active' '创建中'
    $venvPy = Join-Path $base '.venv\Scripts\python.exe'
    if(-not (Test-Path -LiteralPath $venvPy)){
      Invoke-Native $uv @('venv',(Join-Path $base '.venv'),'--python',$pyWant)
    }
    if(-not (Test-Path -LiteralPath $venvPy)){ throw '虚拟环境创建失败' }
    Set-Step 'venv' 'ok' '已创建'

    # 6. 依赖 ---------------------------------------------------------------
    Set-Step 'deps' 'active' '同步中'
    Write-Log 'sys' ('依赖源 ' + $mirror.pypi)
    Invoke-Native $uv @('sync','--project',$base,'--default-index',$mirror.pypi)
    Set-Step 'deps' 'ok' '已同步'

    $shared.current = ''
    $shared.phase = 'done'
    Write-Log 'ok' '环境初始化完成，可以启动基座'
  } catch {
    $msg = $_.Exception.Message
    if($shared.cancel){ $msg = '已取消初始化' }
    $shared.error = $msg
    $shared.phase = 'error'
    $shared.current = ''
    Write-Log 'err' $msg
    foreach($k in @($steps.Keys)){
      try {
        if($steps[$k].state -eq 'active'){ $steps[$k] = [pscustomobject]@{ state = 'fail'; note = $msg } }
      } catch { }
    }
  } finally {
    $shared.finishedAt = Get-Date
  }
}

function Stop-NativeChildren {
  try {
    $procs = @(Get-CimInstance Win32_Process -Filter ('ParentProcessId = ' + $PID) -ErrorAction SilentlyContinue)
    foreach($p in $procs){
      $name = [string]$p.Name
      if($name -notmatch '^(uv|git|git-remote-https|python|pythonw|tar)\.exe$'){ continue }
      try { & taskkill /T /F /PID ([int]$p.ProcessId) 2>&1 | Out-Null } catch { }
    }
  } catch { }
}

function Start-Pipeline {
  if($script:Handle -and -not $script:Handle.IsCompleted){ return $false }
  $profile = Get-MirrorProfile $Config.mirror
  $ctx = @{
    Shared = $Shared
    Steps = $Steps
    Queue = $Queue
    Runtime = $Runtime
    Base = $BaseDir
    Cache = $CacheDir
    Mirror = $profile
    MirrorMode = [string]$Config.mirror
    PythonVersion = [string]$Config.python
    RepoUrl = [string]$Config.repo
    Branch = [string]$Config.branch
    UvPath = $UvLocal
    GitPath = $GitLocal
  }
  $rs = [runspacefactory]::CreateRunspace()
  $rs.Open()
  $ps = [powershell]::Create()
  $ps.Runspace = $rs
  [void]$ps.AddScript($PipelineScript.ToString()).AddArgument($ctx)
  $script:Runspace = $rs
  $script:Pipeline = $ps
  $script:Handle = $ps.BeginInvoke()
  return $true
}

function Complete-PipelineIfDone {
  if(-not $script:Handle){ return }
  if(-not $script:Handle.IsCompleted){ return }
  try { [void]$script:Pipeline.EndInvoke($script:Handle) } catch { }
  try { $script:Pipeline.Dispose() } catch { }
  try { $script:Runspace.Dispose() } catch { }
  $script:Pipeline = $null
  $script:Runspace = $null
  $script:Handle = $null
  if($Shared.phase -eq 'setup'){ $Shared.phase = 'done' }
  $script:StateCache = $null
  $script:StateCacheAt = [DateTime]::MinValue
  $script:VersionCache = $null
  $script:VersionCacheAt = [DateTime]::MinValue
  $script:LocalHead = ''
  $script:LocalHeadAt = [DateTime]::MinValue
}

# ---------------------------------------------------------------------------
# 代码更新管线：git fetch 指定 tag / main → 切换 → uv sync → 记录版本
# ---------------------------------------------------------------------------
$script:UpdatePs = $null
$script:UpdateRunspace = $null
$script:UpdateHandle = $null

$UpdateScript = {
  $ctx = $args[0]
  $ErrorActionPreference = 'Stop'
  try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch { }
  $shared = $ctx.Shared
  $queue = $ctx.Queue
  $base = $ctx.Base
  $ref = $ctx.Ref
  $git = $ctx.GitPath
  $uv = $ctx.UvPath
  $pypi = $ctx.Pypi
  $switched = $false
  $oldSha = ''

  function Log([string]$level,[string]$text){
    $queue.Enqueue([pscustomobject]@{ t = (Get-Date).ToString('HH:mm:ss'); level = $level; text = $text })
  }
  function Run-Git([string[]]$argv){
    Log 'cmd' ('git ' + ($argv -join ' '))
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
      & $git @argv 2>&1 | ForEach-Object {
        $line = ([string]$_).TrimEnd()
        if($line.Length -gt 0){ Log 'out' $line }
      }
      $code = $LASTEXITCODE
    } finally {
      $ErrorActionPreference = $prev
    }
    if($code -ne 0){ throw ('git 命令失败（退出码 ' + $code + '）') }
  }
  function Get-Tip([string]$path){
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
      $value = @(& $git -C $path rev-parse HEAD 2>$null)
    } finally {
      $ErrorActionPreference = $prev
    }
    if(@($value).Count -gt 0){ return ([string]$value[0]).Trim() }
    return ''
  }
  function Sync-Deps {
    Log 'sys' ('同步依赖 · ' + $pypi)
    Log 'cmd' ($uv + ' sync --project ' + $base + ' --default-index ' + $pypi)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
      & $uv sync --project $base --default-index $pypi 2>&1 | ForEach-Object {
        $line = ([string]$_).TrimEnd()
        if($line.Length -gt 0){ Log 'out' $line }
      }
      return $LASTEXITCODE
    } finally {
      $ErrorActionPreference = $prev
    }
  }

  try {
    Log 'sys' ('准备更新到 ' + $ref)
    $oldSha = Get-Tip $base
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { $dirty = @(& $git -C $base status --porcelain --untracked-files=no 2>$null) } finally { $ErrorActionPreference = $prev }
    if(@($dirty).Count -gt 0){ throw '工作区存在本地改动，已取消更新' }

    if($ref -eq 'main'){
      Run-Git @('-C', $base, 'fetch', '--depth', '1', 'origin', 'main')
      Run-Git @('-C', $base, 'checkout', '-f', '-B', 'main', 'FETCH_HEAD')
    } else {
      Run-Git @('-C', $base, 'fetch', '--depth', '1', 'origin', 'tag', $ref)
      Run-Git @('-C', $base, 'checkout', '-f', '--detach', 'FETCH_HEAD')
    }
    $switched = $true
    if($shared.cancel){ throw '已取消更新' }
    $newSha = Get-Tip $base
    $shown = $ref
    if($newSha){ $shown = $ref + ' · ' + $newSha.Substring(0, [Math]::Min(7, $newSha.Length)) }
    Log 'ok' ('代码已切换到 ' + $shown)

    if($shared.cancel){ throw '已取消更新' }
    $syncCode = Sync-Deps
    if($syncCode -ne 0){ throw ('依赖同步失败（退出码 ' + $syncCode + '），已回滚') }
    $entry = Join-Path $base '.venv\Scripts\sllkgui.exe'
    if(-not (Test-Path -LiteralPath $entry)){
      throw ('版本 ' + $ref + ' 不包含 sllkgui 入口，与当前启动器不兼容')
    }

    $rec = [pscustomobject]@{ ref = $ref; sha = $newSha; at = (Get-Date).ToString('s') }
    [IO.File]::WriteAllText((Join-Path $ctx.Runtime 'base-ref.json'), ($rec | ConvertTo-Json -Compress), (New-Object System.Text.UTF8Encoding($false)))
    Log 'ok' ('已更新到 ' + $ref)
    $shared.phase = 'done'
  } catch {
    $msg = $_.Exception.Message
    if($shared.cancel){ $msg = '已取消更新' }
    $shared.error = $msg
    $shared.phase = 'error'
    Log 'err' $msg
    if($oldSha){
      try {
        $prev = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try { & $git -C $base checkout -f $oldSha 2>&1 | Out-Null } finally { $ErrorActionPreference = $prev }
        Log 'warn' ('已回滚到原提交 ' + $oldSha.Substring(0, [Math]::Min(7, $oldSha.Length)))
        if($switched){
          $restore = Sync-Deps
          if($restore -eq 0){ Log 'ok' '已恢复原版本依赖' }
          else { Log 'warn' '回滚后依赖同步失败，请重新初始化环境' }
        }
      } catch { }
    }
  } finally {
    $shared.finishedAt = Get-Date
  }
}

function Start-Update([string]$ref){
  $profile = Get-MirrorProfile $Config.mirror
  $ctx = @{
    Shared = $Shared
    Queue = $Queue
    Base = $BaseDir
    Runtime = $Runtime
    Ref = $ref
    Pypi = $profile.pypi
    UvPath = (Resolve-Tool 'uv' $UvLocal)
    GitPath = (Resolve-Tool 'git' $GitLocal)
  }
  $rs = [runspacefactory]::CreateRunspace()
  $rs.Open()
  $ps = [powershell]::Create()
  $ps.Runspace = $rs
  [void]$ps.AddScript($UpdateScript.ToString()).AddArgument($ctx)
  $script:UpdateRunspace = $rs
  $script:UpdatePs = $ps
  $script:UpdateHandle = $ps.BeginInvoke()
}

function Complete-UpdateIfDone {
  if(-not $script:UpdateHandle){ return }
  if(-not $script:UpdateHandle.IsCompleted){ return }
  try { [void]$script:UpdatePs.EndInvoke($script:UpdateHandle) } catch { }
  try { $script:UpdatePs.Dispose() } catch { }
  try { $script:UpdateRunspace.Dispose() } catch { }
  $script:UpdatePs = $null
  $script:UpdateRunspace = $null
  $script:UpdateHandle = $null
  if($Shared.phase -eq 'update'){ $Shared.phase = 'done' }
  $script:StateCache = $null
  $script:StateCacheAt = [DateTime]::MinValue
  $script:VersionCache = $null
  $script:LocalHead = ''
  $script:LocalHeadAt = [DateTime]::MinValue
}

function Start-BaseApp {
  if(Test-AppRunning){
    return [pscustomobject]@{ ok = $true; pid = (Get-BaseProcessId); already = $true }
  }
  $envState = Get-State
  if(-not $envState.ready){
    return [pscustomobject]@{ ok = $false; error = '环境尚未就绪' }
  }
  try {
    $outLog = Join-Path $LogDir 'app.out.log'
    $errLog = Join-Path $LogDir 'app.err.log'
    $dataDir = Join-Path $Runtime 'data'
    if(-not (Test-Path -LiteralPath $dataDir)){ New-Item -ItemType Directory -Force -Path $dataDir | Out-Null }
    $mode = [string]$Config.mode
    if($mode -ne 'gallery'){ $mode = 'run' }
    # 通过 cmd 隐藏控制台并重定向输出，避免出现任何 PowerShell / 控制台窗口
    $line = '/d /c ""' + $envState.uv + '" run --project "' + $BaseDir + '" --no-sync sllkgui ' + $mode + ' --data-dir "' + $dataDir + '" > "' + $outLog + '" 2> "' + $errLog + '""'
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $env:ComSpec
    $psi.Arguments = $line
    $psi.WorkingDirectory = $BaseDir
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
    $proc = [System.Diagnostics.Process]::Start($psi)
    $script:AppProcess = $proc
    $Queue.Enqueue([pscustomobject]@{ t = (Get-Date).ToString('HH:mm:ss'); level = 'ok'; text = ('基座已启动 · PID ' + $proc.Id) })
    return [pscustomobject]@{ ok = $true; pid = [int]$proc.Id; already = $false }
  } catch {
    return [pscustomobject]@{ ok = $false; error = $_.Exception.Message }
  }
}

# ---------------------------------------------------------------------------
# 页面入口：交给系统默认浏览器，不捆绑任何浏览器内核
# ---------------------------------------------------------------------------
function Open-Page([string]$url){
  try { Start-Process $url; return $true } catch { return $false }
}

function Show-Dialog([string]$text,[string]$title,[string]$icon){
  try {
    Add-Type -AssemblyName System.Windows.Forms | Out-Null
    [Windows.Forms.MessageBox]::Show($text, $title, 'OK', $icon) | Out-Null
  } catch { }
}

# ---------------------------------------------------------------------------
# 极简本地 HTTP 服务（仅回环，无管理员权限、无第三方依赖）
# ---------------------------------------------------------------------------
function Read-Request($stream){
  $ms = New-Object System.IO.MemoryStream
  $buf = New-Object byte[] 4096
  $headerEnd = -1
  while($true){
    $n = $stream.Read($buf,0,$buf.Length)
    if($n -le 0){ break }
    $ms.Write($buf,0,$n)
    $bytes = $ms.ToArray()
    for($i = 0; $i -le ($bytes.Length - 4); $i++){
      if($bytes[$i] -eq 13 -and $bytes[$i+1] -eq 10 -and $bytes[$i+2] -eq 13 -and $bytes[$i+3] -eq 10){ $headerEnd = $i; break }
    }
    if($headerEnd -ge 0){ break }
    if($ms.Length -gt 1048576){ break }
  }
  if($headerEnd -lt 0){ return $null }
  $all = $ms.ToArray()
  $headerText = [Text.Encoding]::ASCII.GetString($all,0,$headerEnd)
  $lines = $headerText -split "`r`n"
  $first = $lines[0] -split ' '
  if($first.Length -lt 2){ return $null }
  $headers = @{}
  foreach($h in ($lines | Select-Object -Skip 1)){
    $idx = $h.IndexOf(':')
    if($idx -gt 0){
      $key = $h.Substring(0,$idx).Trim().ToLower()
      $val = $h.Substring($idx + 1).Trim()
      $headers[$key] = $val
    }
  }
  $len = 0
  if($headers.ContainsKey('content-length')){ try { $len = [int]$headers['content-length'] } catch { } }
  $bodyStart = $headerEnd + 4
  $body = ''
  if($len -gt 0){
    $have = $all.Length - $bodyStart
    while($have -lt $len){
      $n = $stream.Read($buf,0,$buf.Length)
      if($n -le 0){ break }
      $ms.Write($buf,0,$n)
      $all = $ms.ToArray()
      $have = $all.Length - $bodyStart
    }
    if($have -gt 0){
      $take = [Math]::Min($len,$have)
      $body = [Text.Encoding]::UTF8.GetString($all,$bodyStart,$take)
    }
  }
  return [pscustomobject]@{ method = $first[0]; path = $first[1]; headers = $headers; body = $body }
}

$Reasons = @{ 200 = 'OK'; 204 = 'No Content'; 400 = 'Bad Request'; 403 = 'Forbidden'; 404 = 'Not Found'; 500 = 'Internal Server Error' }

function Send-Bytes($stream,[int]$status,[string]$ctype,[byte[]]$bytes){
  $reason = $Reasons[$status]
  if(-not $reason){ $reason = 'OK' }
  $head = 'HTTP/1.1 ' + $status + ' ' + $reason + "`r`nContent-Type: " + $ctype + "`r`nContent-Length: " + $bytes.Length + "`r`nCache-Control: no-store`r`nConnection: close`r`n`r`n"
  $hb = [Text.Encoding]::ASCII.GetBytes($head)
  $stream.Write($hb,0,$hb.Length)
  if($bytes.Length -gt 0){ $stream.Write($bytes,0,$bytes.Length) }
  $stream.Flush()
}
function Send-Json($stream,$obj){
  Send-Bytes $stream 200 'application/json; charset=utf-8' ([Text.Encoding]::UTF8.GetBytes(($obj | ConvertTo-Json -Depth 8 -Compress)))
}
function Send-Text($stream,[int]$status,[string]$text){
  Send-Bytes $stream $status 'text/plain; charset=utf-8' ([Text.Encoding]::UTF8.GetBytes($text))
}

function Drain-Queue {
  $item = $null
  $sb = New-Object System.Text.StringBuilder
  while($Queue.TryDequeue([ref]$item)){
    [void]$LogLines.Add($item)
    [void]$sb.AppendLine($item.t + ' [' + $item.level + '] ' + $item.text)
  }
  if($sb.Length -gt 0){
    try {
      $logPath = Join-Path $LogDir 'launcher.log'
      if((Test-Path -LiteralPath $logPath) -and ((Get-Item -LiteralPath $logPath).Length -gt 2097152)){
        Move-Item -LiteralPath $logPath -Destination ($logPath + '.1') -Force
      }
      Add-Content -LiteralPath $logPath -Value $sb.ToString() -Encoding UTF8
    } catch { }
  }
  if($LogLines.Count -gt 5000){
    try {
      $drop = $LogLines.Count - 2000
      $LogLines.RemoveRange(0, $drop)
      $script:LogDropped = $script:LogDropped + $drop
    } catch { }
  }
}

$FaviconB64 = 'iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJcEhZcwAADsMAAA7DAcdvqGQAAAVVSURBVFhH7ZZ7TFNnGMZJtmTJNNt0WZxxYyoL25DJrdBKkQoCoqgLmS03W5ACBUq5WMQKIk4QWsDhBVAnVxWQDgmCIIWWCrUilNJyv4yrOjWaOclMUCY+S09izE4Wh8wlW8IvOTnnj/M+73Pey8lnZLTAAv9XrANoX69lWXmbM61Z1r5UGwaD8Tb5nX8FV6HrIgqHKnUM2wBWGgvMw0y4xLiBGrBu0NLHRsQIZywmx7xRqL621V4SL5wf+wGKmSrUTpWjaOgkDtSIwExlwnqn7TCFTXMhx70R/DeZFjiHM1A0fBIl42fwXW0Cmp/X4ER7BiILw9E4XQlRhRB0niNs2bRQcvw/Ipq6In2Xx1fYnLAdlx9dQOW9c2Ae2oE0+UFU/1KKuPIYoiIq1OJAzT7QguiwZVODyTrzItTeOCjRzRQn4r+Bm2grkbAFl1H76AJO6bIgLI0ENycAJzrTkd+XjYAsNpLrE7EuyGHWhkOzI+u9FkLGavNg6orf65O+xa26JDiGO+F7dRqiiyNwWn8U8dWxyCo+jrYuDfjpAgTmclA2kYdW1CNOGgMLL5suppT5Fll3zgSt+0QlZlljujEZs1fTwBK4ILQonCh9ZksKRFUxyLtYAAPT008QIuEhf/A4CgZyUNCfDY/4rbD2tfUl684JAcPEne9gjOYMNnA9E2gWozw7CFS+M+p/+xHKZ9W49LAEPqk+UGnUhImyOikE53nYUxYNfh4PMSUCWPvZNpG150SYw8qK/R5muF8Vj2fKVMzIU/BUcRgs/kZwcrnEHGRrMhF1jo+dGX5IPJUE7uFgZGszoEYdsRWnu46BGmA/RePSlpL1X4nA/fN3QuyNb0m8KXgqT8ETeQrRBlxNw8DFvaBwaIir3EOsn2HwrjyW4mC9CAVD2UhXJmNv+W5iKwzzsIHvDMsdlmbkHK8k0nnVMh7d+LHYi4KnipcGCBMtEsgLI2DuQ8Gei7G4OltNVCOqiI9jrRJiS5jJTOJZersQ9OD1sxZeFivJOV6JP+OzD/iOKx/GuX+JB5cSiBa8MECYUEmgLI4EjUODp8QbFXeKiS/PaE4h/gV1U+XEFV8VZxjCLiZzHpsgcFp9I5z+KZrEfkBrJqYbXhp4UYmJSwkIEW6GFZcOdm4g0q+lIn8wF/kDORBKd4MRxoA9h7qdrD0nBE4mgtiNJhBtMcOj2gN43iz+kwHChDKVmIumIgGi9m7DNv5GuEe5wjHQHm7eNtjmaRFN1p0zSVuXvxvpZDJmWMWjAXTMNKX+pYknBiPNYkCThSnZIeTwnRG6YdVMtIMxm6z52mwyMvoigvbRvSC75TjqT8fDmkSiHQYjhrmYNSRWZ+B5iwQ9Z8Ig9lyDMLuPf/JeZLSWrPXaZEuli9sfTG0vOJ2lF7qYwt9iCUSbzVB3iIWxkt24V7kPE2VCqI74I8PLEoFWS5Es8EOdWj3ZMjKZ39TTwy2Vy5eRdedEQ0cHTdnbf7N1ZAzXRiZRVlGGfUwHcK2WgG3+Hnh2yyBwWIEQyoeEsdgd63H2bB4UvUNQ9g1CPTyCGyNjaOkb+PVKWweLrP+31Gs0rs29A8/axiagGhiCangMDVodCs8chziGg6RdHjgY7IkjCRE4X1qIBl03mvqH0dCph0LfjZb+QbSNjuPG6DiuaLTzOxtcVrWvVnb17JfruhWyDt3PDZ362evjt9F+8y7aJg33O+i48wCaW3ehHh4lkhpMyjp09xt1XWpFd6+kSq22IuvOC5lev6hRrzeVdeidG3Q6Zr1WHyjT6HgyrZYn03RyZVqtt0yjc1Po+tY0jo6+T45fYIH/LH8ACZ2eNucM4EgAAAAASUVORK5CYII='

function Get-AppLogTail([int]$max){
  $file = $null
  $dir = Join-Path $Runtime 'data\logs'
  if(Test-Path -LiteralPath $dir){
    $f = Get-ChildItem -LiteralPath $dir -Filter *.log -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if($f){ $file = $f.FullName }
  }
  if(-not $file){
    foreach($c in @((Join-Path $LogDir 'app.err.log'), (Join-Path $LogDir 'app.out.log'))){
      if((Test-Path -LiteralPath $c) -and (Get-Item -LiteralPath $c).Length -gt 0){ $file = $c; break }
    }
  }
  if(-not $file){ return [pscustomobject]@{ file = ''; lines = @() } }
  $lines = @()
  try { $lines = @(Get-Content -LiteralPath $file -Tail $max -Encoding UTF8) } catch { }
  $esc = [string][char]27
  $pattern = $esc + '\[[0-9;]*m'
  $clean = @()
  foreach($l in $lines){ $clean += [regex]::Replace([string]$l, $pattern, '') }
  return [pscustomobject]@{ file = (Split-Path -Leaf $file); lines = $clean }
}

function Register-Client([string]$sid){
  if(-not $sid){ return }
  $script:Clients[$sid] = Get-Date
  if($script:Clients.Count -gt 24){
    foreach($k in @($script:Clients.Keys)){
      if(((Get-Date) - $script:Clients[$k]).TotalSeconds -gt 300){ [void]$script:Clients.Remove($k) }
    }
  }
}

function Test-ClientAlive([string]$except){
  foreach($k in @($script:Clients.Keys)){
    if($k -eq $except){ continue }
    if(((Get-Date) - $script:Clients[$k]).TotalSeconds -le 5){ return $true }
  }
  return $false
}

function Handle-Request($stream,$req){
  $path = [string]$req.path
  $query = ''
  $qi = $path.IndexOf('?')
  if($qi -ge 0){ $query = $path.Substring($qi + 1); $path = $path.Substring(0,$qi) }
  if($path -eq '/' -or $path -eq '/index.html'){ $script:ByeAt = $null }

  if($path -eq '/favicon.ico'){
    try {
      Send-Bytes $stream 200 'image/png' ([Convert]::FromBase64String($FaviconB64))
    } catch {
      Send-Bytes $stream 204 'image/x-icon' ([byte[]]@())
    }
    return
  }

  if($path -eq '/' -or $path -eq '/index.html'){
    $html = $HtmlTemplate.Replace('__TOKEN__', $script:Token)
    Send-Bytes $stream 200 'text/html; charset=utf-8' ([Text.Encoding]::UTF8.GetBytes($html))
    return
  }

  $sid = ''
  if($query -match 'sid=([A-Za-z0-9._\-]{1,40})'){ $sid = $Matches[1] }

  if($path.StartsWith('/api/')){
    if($req.headers['x-token'] -ne $script:Token){
      Send-Bytes $stream 403 'application/json; charset=utf-8' ([Text.Encoding]::UTF8.GetBytes('{"ok":false,"error":"forbidden"}'))
      return
    }
    if($sid -and $path -ne '/api/bye'){ Register-Client $sid }
  }

  switch($path){
    '/api/state' { Send-Json $stream (Build-State); return }
    '/api/versions' {
      $refresh = [bool]($query -match 'refresh=1')
      Send-Json $stream (Get-VersionState $refresh $false)
      return
    }
    '/api/update' {
      $body = $null
      if($req.body){ try { $body = $req.body | ConvertFrom-Json } catch { } }
      $ref = ''
      if($body -and $body.ref){ $ref = [string]$body.ref }
      if(-not $ref){
        Send-Json $stream ([pscustomobject]@{ ok = $false; error = '缺少版本号' })
        return
      }
      if($ref -notmatch '^[A-Za-z0-9][A-Za-z0-9._\-]*$'){
        Send-Json $stream ([pscustomobject]@{ ok = $false; error = '版本号不合法' })
        return
      }
      if($Shared.phase -eq 'setup' -or $Shared.phase -eq 'update'){
        Send-Json $stream ([pscustomobject]@{ ok = $false; error = '启动器正忙，请稍后再试' })
        return
      }
      if($script:Handle -and -not $script:Handle.IsCompleted){
        Send-Json $stream ([pscustomobject]@{ ok = $false; error = '启动器正忙，请稍后再试' })
        return
      }
      if(Test-AppRunning){
        Send-Json $stream ([pscustomobject]@{ ok = $false; error = '基座正在运行，请先关闭基座再更新' })
        return
      }
      if(-not (Test-Path -LiteralPath (Join-Path $BaseDir '.git'))){
        Send-Json $stream ([pscustomobject]@{ ok = $false; error = '尚未拉取源码' })
        return
      }
      $remote = Get-RemoteVersions $false
      if(-not $remote.ok){
        Send-Json $stream ([pscustomobject]@{ ok = $false; error = $remote.error })
        return
      }
      $exists = $false
      if($ref -eq 'main'){
        $exists = [bool]$remote.mainSha
      } else {
        foreach($t in @($remote.tags)){
          if($t.name -eq $ref){ $exists = $true; break }
        }
      }
      if(-not $exists){
        Send-Json $stream ([pscustomobject]@{ ok = $false; error = '版本不存在或已从仓库删除' })
        return
      }
      $Shared.phase = 'update'
      $Shared.cancel = $false
      $Shared.updateRef = $ref
      $Shared.error = ''
      $Shared.current = ''
      $Shared.startedAt = Get-Date
      $Shared.finishedAt = $null
      $script:StateCache = $null
      try {
        Start-Update $ref
      } catch {
        $Shared.phase = 'error'
        $Shared.error = $_.Exception.Message
        $Shared.finishedAt = Get-Date
        Send-Json $stream ([pscustomobject]@{ ok = $false; error = $Shared.error })
        return
      }
      Send-Json $stream ([pscustomobject]@{ ok = $true; ref = $ref })
      return
    }
    '/api/update/stop' {
      if($script:UpdatePs -and $script:UpdateHandle -and -not $script:UpdateHandle.IsCompleted){
        $Shared.cancel = $true
        Stop-NativeChildren
        try { $script:UpdatePs.Stop() } catch { }
        $Shared.phase = 'error'
        $Shared.error = '已取消更新'
        $Shared.finishedAt = Get-Date
        $Queue.Enqueue([pscustomobject]@{ t = (Get-Date).ToString('HH:mm:ss'); level = 'warn'; text = '用户取消了代码更新' })
      }
      Send-Json $stream ([pscustomobject]@{ ok = $true })
      return
    }
    '/api/applog' {
      $bp = Get-BaseProcess
      if(-not $bp.owned){
        Send-Json $stream ([pscustomobject]@{ file = ''; lines = @() })
        return
      }
      Send-Json $stream (Get-AppLogTail 180)
      return
    }
    '/api/log' {
      Drain-Queue
      $cursor = 0
      if($query -match 'cursor=(\d+)'){ $cursor = [int]$Matches[1] }
      $total = $script:LogDropped + $LogLines.Count
      if($cursor -lt 0){ $cursor = 0 }
      if($cursor -gt $total){ $cursor = $total }
      $from = $cursor - $script:LogDropped
      if($from -lt 0){ $from = 0 }
      if($from -gt $LogLines.Count){ $from = $LogLines.Count }
      $lines = @()
      if($LogLines.Count -gt $from){ $lines = @($LogLines.GetRange($from, $LogLines.Count - $from)) }
      Send-Json $stream ([pscustomobject]@{ cursor = $total; lines = $lines })
      return
    }
    '/api/config' {
      $body = $null
      if($req.body){ try { $body = $req.body | ConvertFrom-Json } catch { } }
      if($body -and ($body.mirror -eq 'cn' -or $body.mirror -eq 'global')){
        $Config.mirror = [string]$body.mirror
        Save-Config
      }
      Send-Json $stream (Build-State)
      return
    }
    '/api/mode' {
      $body = $null
      if($req.body){ try { $body = $req.body | ConvertFrom-Json } catch { } }
      $mode = ''
      if($body -and $body.mode){ $mode = [string]$body.mode }
      if($mode -ne 'run' -and $mode -ne 'gallery'){
        Send-Json $stream ([pscustomobject]@{ ok = $false; error = '模式参数不合法' })
        return
      }
      if(Test-AppRunning){
        Send-Json $stream ([pscustomobject]@{ ok = $false; error = '基座正在运行，不能切换模式' })
        return
      }
      $Config.mode = $mode
      Save-Config
      Send-Json $stream ([pscustomobject]@{ ok = $true; mode = $mode })
      return
    }
    '/api/setup' {
      if($Shared.phase -eq 'setup' -or $Shared.phase -eq 'update'){
        Send-Json $stream ([pscustomobject]@{ ok = $false; error = 'busy' })
        return
      }
      if($script:Handle -and -not $script:Handle.IsCompleted){
        Send-Json $stream ([pscustomobject]@{ ok = $false; error = 'busy' })
        return
      }
      if(Test-AppRunning){
        Send-Json $stream ([pscustomobject]@{ ok = $false; error = '基座正在运行，请先关闭基座再初始化' })
        return
      }
      $script:Steps.Clear()
      $Shared.cancel = $false
      $Shared.error = ''
      $Shared.current = ''
      $Shared.finishedAt = $null
      $Shared.startedAt = Get-Date
      $Shared.phase = 'setup'
      $script:StateCache = $null
      $started = $false
      try { $started = Start-Pipeline } catch { $Shared.error = $_.Exception.Message }
      if(-not $started){
        $Shared.phase = 'error'
        if(-not $Shared.error){ $Shared.error = '已有初始化任务在运行' }
        Send-Json $stream ([pscustomobject]@{ ok = $false; error = $Shared.error })
        return
      }
      Send-Json $stream ([pscustomobject]@{ ok = $true })
      return
    }
    '/api/setup/stop' {
      if($script:Pipeline -and $script:Handle -and -not $script:Handle.IsCompleted){
        $Shared.cancel = $true
        Stop-NativeChildren
        try { $script:Pipeline.Stop() } catch { }
        $Shared.phase = 'error'
        $Shared.error = '已取消初始化'
        $Shared.finishedAt = Get-Date
        $Queue.Enqueue([pscustomobject]@{ t = (Get-Date).ToString('HH:mm:ss'); level = 'warn'; text = '用户取消了初始化' })
      }
      Send-Json $stream ([pscustomobject]@{ ok = $true })
      return
    }
    '/api/launch' { Send-Json $stream (Start-BaseApp); return }
    '/api/open' {
      try { Start-Process explorer.exe $LogDir } catch { }
      Send-Json $stream ([pscustomobject]@{ ok = $true })
      return
    }
    '/api/exit' {
      if($Shared.phase -eq 'setup' -or $Shared.phase -eq 'update'){
        Send-Json $stream ([pscustomobject]@{ ok = $false; error = '初始化或更新进行中，请先停止后再退出' })
        return
      }
      $script:Shutdown = $true
      Send-Json $stream ([pscustomobject]@{ ok = $true })
      return
    }
    '/api/bye' {
      if($sid){ [void]$script:Clients.Remove($sid) }
      if(-not (Test-ClientAlive $sid)){ $script:ByeAt = Get-Date }
      Send-Json $stream ([pscustomobject]@{ ok = $true })
      return
    }
  }
  if($path.StartsWith('/api/')){ Send-Json $stream ([pscustomobject]@{ ok = $false; error = 'not found' }); return }
  Send-Text $stream 404 'not found'
}

# ---------------------------------------------------------------------------
# 单页面 UI（内嵌，零外部资源）
# ---------------------------------------------------------------------------
$HtmlTemplate = @'
<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<link rel="icon" type="image/png" href="/favicon.ico">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark">
<title>SllkGui 启动器</title>
<style>
:root{
  --bg:#121619;--panel:#171c1f;--panel2:#0d1113;--line:#262b2d;--line2:#333739;
  --txt:#dfe6df;--title:#f4f7f3;--dim:#98a59b;--dim2:#6f7b73;
  --accent:#a3e57f;--accent2:#b7ee99;--accent-soft:rgba(163,229,127,.12);
  --warn:#f2c65a;--mint:#6fd08c;--red:#ff8f87;--blue:#9db7a9;
  --fd:"Bahnschrift","DIN Alternate","Segoe UI Variable Display","Microsoft YaHei UI",sans-serif;
  --fb:"Segoe UI Variable","Microsoft YaHei UI","PingFang SC","Segoe UI",sans-serif;
  --fm:"Cascadia Mono","Cascadia Code",Consolas,"SF Mono",Menlo,monospace;
}
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;background:var(--bg);color:var(--txt);font-family:var(--fb);font-size:14px;
  -webkit-font-smoothing:antialiased;overflow:hidden}
body::after{content:"";position:fixed;inset:0;pointer-events:none;z-index:0;
  background:radial-gradient(620px 380px at 78% -12%,rgba(163,229,127,.07),transparent 70%),
             radial-gradient(720px 460px at 4% 108%,rgba(157,183,169,.05),transparent 70%)}
.grid{position:fixed;inset:0;pointer-events:none;z-index:0;
  background-image:linear-gradient(to right,rgba(223,230,223,.03) 1px,transparent 1px),
                   linear-gradient(to bottom,rgba(223,230,223,.03) 1px,transparent 1px);
  background-size:56px 56px;
  -webkit-mask-image:radial-gradient(ellipse 92% 72% at 62% -8%,#000 0%,transparent 76%);
  mask-image:radial-gradient(ellipse 92% 72% at 62% -8%,#000 0%,transparent 76%)}
::selection{background:rgba(163,229,127,.26)}
.shell{position:relative;z-index:1;height:100vh;max-width:1280px;margin:0 auto;
  padding:20px 26px 12px;display:flex;flex-direction:column;gap:13px}
/* ---------- top ---------- */
.top{display:flex;align-items:center;justify-content:space-between;gap:18px;min-height:34px}
.brand{display:flex;align-items:center;gap:10px;font-family:var(--fd);letter-spacing:.14em;font-size:14px}
.brand .kiwi{width:19px;height:19px;display:block}
.brand .name{font-weight:600}
.top-right{display:flex;align-items:center;gap:12px}
.mirror-label{font-size:11.5px;color:var(--dim2)}
.mirror{position:relative;display:flex;border:1px solid var(--line2);padding:2px;background:var(--panel2)}
.mirror button{position:relative;z-index:2;border:0;background:transparent;color:var(--dim);
  font-family:var(--fb);font-size:12px;padding:6px 13px;cursor:pointer;transition:color .18s}
.mirror button.on{color:#10140f;font-weight:600}
.mirror .thumb{position:absolute;z-index:1;top:2px;bottom:2px;left:2px;width:calc(50% - 2px);
  background:var(--accent);transition:transform .26s cubic-bezier(.4,.8,.2,1)}
.mirror[data-m="global"] .thumb{transform:translateX(100%)}
.mirror[data-m="gallery"] .thumb{transform:translateX(100%)}
.mirror button:disabled{opacity:.42;cursor:not-allowed}
.mirror button:focus-visible{outline:2px solid var(--accent2);outline-offset:3px}
.saved{font-family:var(--fm);font-size:10px;color:var(--mint);opacity:0;transition:opacity .3s;min-width:44px}
.saved.show{opacity:1}
.saved.bad{color:var(--red)}
/* ---------- layout ---------- */
main{display:grid;grid-template-columns:308px minmax(0,1fr);gap:13px;flex:1;min-height:0}
.panel{position:relative;background:var(--panel);border:1px solid var(--line)}
.panel::before,.panel::after{content:"";position:absolute;width:6px;height:6px;border:1px solid var(--line2)}
.panel::before{top:-1px;left:-1px;border-right:0;border-bottom:0}
.panel::after{bottom:-1px;right:-1px;border-left:0;border-top:0}
.panel-head{display:flex;align-items:center;justify-content:space-between;
  padding:12px 16px;border-bottom:1px solid var(--line);font-size:12px;color:var(--dim)}
.panel-head .count{font-family:var(--fm);font-size:10.5px;color:var(--accent)}
/* ---------- rail ---------- */
.rail{display:flex;flex-direction:column;min-height:0}
.steps{list-style:none;margin:0;padding:6px 0;flex:1;overflow:auto;position:relative}
.steps::before{content:"";position:absolute;left:23px;top:20px;bottom:20px;width:1px;
  background:linear-gradient(var(--line2),var(--line))}
.step{position:relative;display:grid;grid-template-columns:8px 22px 1fr auto;align-items:center;
  gap:10px;padding:13px 16px 13px 20px;transition:background .2s}
.step .dot{width:7px;height:7px;transform:rotate(45deg);background:var(--panel);
  border:1px solid var(--line2);justify-self:center;transition:all .2s}
.step .idx{font-family:var(--fm);font-size:9.5px;color:var(--dim2)}
.step .lbl{font-size:13px;color:var(--dim);transition:color .2s}
.step .note{font-family:var(--fm);font-size:10px;color:var(--dim2);max-width:104px;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;text-align:right}
.step[data-s="ok"] .dot{background:var(--mint);border-color:var(--mint)}
.step[data-s="ok"] .lbl{color:var(--txt)}
.step[data-s="ok"] .note{color:var(--mint);opacity:.75}
.step[data-s="active"]{background:linear-gradient(90deg,rgba(163,229,127,.09),transparent 78%)}
.step[data-s="active"] .dot{background:var(--accent);border-color:var(--accent);
  box-shadow:0 0 0 4px rgba(163,229,127,.14);animation:pulse 1.7s ease-in-out infinite}
.step[data-s="active"] .lbl{color:var(--accent)}
.step[data-s="active"] .note{color:var(--accent)}
.step[data-s="fail"] .dot{background:var(--red);border-color:var(--red)}
.step[data-s="fail"] .lbl,.step[data-s="fail"] .note{color:var(--red)}
/* ---------- stage ---------- */
.stage{display:flex;flex-direction:column;gap:13px;min-height:0}
.hero{padding:26px 28px 22px;display:flex;flex-direction:column}
h1{margin:0 0 10px;font-family:var(--fd);font-size:56px;line-height:.94;font-weight:600;
  letter-spacing:-.015em;color:var(--txt);transition:color .3s}
body[data-phase="setup"] h1{color:var(--accent)}
body[data-phase="update"] h1{color:var(--accent)}
body[data-phase="running"] h1{color:var(--mint)}
body[data-phase="error"] h1{color:var(--red)}
.desc{margin:0;font-size:13px;line-height:1.7;color:var(--dim);max-width:66ch;min-height:44px}
.actions{display:flex;gap:9px;margin-top:16px;flex-wrap:wrap}
.btn{height:40px;padding:0 18px;border:1px solid var(--line2);background:transparent;color:var(--txt);
  font-family:var(--fb);font-size:13px;letter-spacing:.02em;cursor:pointer;display:inline-flex;
  align-items:center;gap:9px;transition:background .18s,border-color .18s,color .18s,transform .12s}
.btn:hover{background:#20272a;border-color:var(--dim2)}
.btn:active{transform:translateY(1px)}
.btn:disabled{opacity:.45;cursor:not-allowed}
.btn.primary{background:var(--accent);border-color:var(--accent);color:#10140f;font-weight:600;min-width:132px;justify-content:center}
.btn.primary:hover{background:var(--accent2);border-color:var(--accent2)}
.btn.primary .arw{width:14px;height:14px;stroke:currentColor;stroke-width:1.8;fill:none;transition:transform .2s}
.btn.primary:hover .arw{transform:translateX(3px)}
.btn.ghost{color:var(--dim);font-size:12.5px}
.btn.ghost:hover{color:var(--txt)}
.btn:focus-visible{outline:2px solid var(--accent2);outline-offset:2px}
/* progress */
.progress{margin-top:18px}
.ptrack{height:2px;background:var(--panel2);position:relative;overflow:hidden}
.ptrack i{display:block;height:100%;width:0;background:linear-gradient(90deg,var(--accent),var(--accent2));
  transition:width .45s cubic-bezier(.4,.8,.2,1)}
.ptrack i::after{content:"";position:absolute;top:0;bottom:0;width:90px;
  background:linear-gradient(90deg,transparent,rgba(255,255,255,.55),transparent);animation:sheen 1.9s linear infinite}
.pmeta{display:flex;justify-content:space-between;margin-top:8px;font-family:var(--fm);
  font-size:10px;color:var(--dim2);letter-spacing:.06em}
/* facts */
.facts{display:grid;grid-template-columns:repeat(6,1fr);gap:1px;background:var(--line);
  border:1px solid var(--line)}
.fact{background:var(--panel);padding:10px 13px;display:flex;flex-direction:column;gap:6px;min-width:0}
.fact .fk{font-family:var(--fm);font-size:9px;letter-spacing:.16em;color:var(--dim2);text-transform:uppercase}
.fact .fv{font-family:var(--fm);font-size:11.5px;color:var(--dim);overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap}
.fact[data-s="ok"] .fv{color:var(--txt)}
.fact[data-s="fail"] .fv{color:var(--red)}
.fact[data-s="active"] .fv{color:var(--accent)}
/* ---------- version ---------- */
.version{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:0 16px;height:46px;flex:0 0 auto}
.v-info{display:flex;align-items:center;gap:9px;min-width:0}
.v-k{font-family:var(--fm);font-size:9px;letter-spacing:.18em;color:var(--dim2)}
.v-ref{font-family:var(--fm);font-size:12px;color:var(--txt);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.v-sha{font-family:var(--fm);font-size:10px;color:var(--dim2)}
.v-flag{font-size:9.5px;letter-spacing:.08em;padding:2px 6px;border:1px solid transparent;white-space:nowrap}
.v-flag.warn{color:var(--warn);border-color:rgba(242,198,90,.35);background:rgba(242,198,90,.12)}
.v-flag.new{color:var(--accent);border-color:rgba(163,229,127,.32);background:var(--accent-soft)}
.v-right{display:flex;align-items:center;gap:12px;min-width:0}
.v-latest{font-family:var(--fm);font-size:10px;color:var(--dim2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:220px}
.v-open{background:transparent;border:1px solid var(--line2);color:var(--dim);font-family:var(--fb);font-size:11.5px;padding:5px 11px;cursor:pointer;transition:color .18s,border-color .18s}
.v-open:hover{color:var(--txt);border-color:var(--dim2)}
.v-open:disabled{opacity:.4;cursor:not-allowed}
/* ---------- modal ---------- */
.modal{position:fixed;inset:0;z-index:20;display:flex;align-items:center;justify-content:center}
.modal[hidden]{display:none}
.modal-mask{position:absolute;inset:0;background:rgba(13,17,19,.66)}
.modal-card{position:relative;width:min(560px,calc(100vw - 48px));max-height:min(640px,calc(100vh - 96px));background:var(--panel);border:1px solid var(--line2);box-shadow:0 24px 60px rgba(0,0,0,.55);display:flex;flex-direction:column;animation:pop .18s ease both}
.m-head{display:flex;align-items:center;justify-content:space-between;padding:15px 18px;border-bottom:1px solid var(--line)}
.m-title{font-family:var(--fd);font-size:15px;letter-spacing:.04em;color:var(--title)}
.m-close{background:transparent;border:0;color:var(--dim2);font-size:20px;line-height:1;cursor:pointer;padding:0 2px}
.m-close:hover{color:var(--txt)}
.m-body{padding:14px 18px 6px;overflow:auto;display:flex;flex-direction:column;gap:10px;min-height:0}
.m-meta{display:flex;align-items:center;justify-content:space-between;gap:12px}
.m-repo{font-family:var(--fm);font-size:10px;color:var(--dim2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.m-refresh{background:transparent;border:0;color:var(--dim2);font-family:var(--fm);font-size:10px;cursor:pointer;padding:0}
.m-refresh:hover{color:var(--accent)}
.m-current{font-size:12px;color:var(--dim)}
.m-list{display:flex;flex-direction:column;border:1px solid var(--line);max-height:320px;overflow:auto}
.vrow{display:grid;grid-template-columns:14px 1fr auto;align-items:center;gap:10px;padding:11px 12px;background:transparent;border:0;border-bottom:1px solid rgba(223,230,223,.05);color:var(--txt);font-family:var(--fb);font-size:13px;text-align:left;cursor:pointer;transition:background .16s}
.vrow:last-child{border-bottom:0}
.vrow:hover{background:#20272a}
.vrow[aria-pressed="true"]{background:var(--accent-soft);box-shadow:inset 2px 0 0 var(--accent)}
.radio{width:9px;height:9px;border:1px solid var(--line2);border-radius:50%;justify-self:center}
.vrow[aria-pressed="true"] .radio{border-color:var(--accent);background:var(--accent);box-shadow:0 0 0 3px rgba(163,229,127,.14)}
.vlabel{display:flex;align-items:center;gap:8px;min-width:0;font-family:var(--fm);font-size:12px}
.vlabel>span:first-child{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.vdev{font-family:var(--fm);font-size:9px;letter-spacing:.1em;color:var(--warn);border:1px solid rgba(242,198,90,.35);background:rgba(242,198,90,.12);padding:1px 5px;font-style:normal}
.vsha2{font-family:var(--fm);font-size:10px;color:var(--dim2)}
.vchips{display:flex;align-items:center;gap:6px}
.chip{font-family:var(--fm);font-size:9px;letter-spacing:.06em;padding:1px 5px;border:1px solid var(--line2);color:var(--dim2);white-space:nowrap}
.chip.cur{color:var(--accent);border-color:rgba(163,229,127,.32)}
.chip.latest{color:var(--mint);border-color:rgba(111,208,140,.30)}
.m-note{font-size:11.5px;color:var(--warn);padding:2px 0 8px;line-height:1.6}
.m-foot{display:flex;justify-content:flex-end;gap:9px;padding:12px 18px 16px;border-top:1px solid var(--line)}
.m-foot .btn{height:36px;font-size:12.5px}
.busy{color:var(--dim2);font-family:var(--fm);font-size:11px;padding:16px;text-align:center}
/* console */
.console{flex:1;min-height:148px;display:flex;flex-direction:column;overflow:hidden}
.console .panel-head{padding:10px 15px}
.chead-right{display:flex;align-items:center;gap:12px;font-family:var(--fm);font-size:10px;color:var(--dim2)}
.live{width:5px;height:5px;border-radius:50%;background:var(--dim2);display:inline-block;margin-left:7px;
  vertical-align:middle;transition:background .2s}
body[data-phase="setup"] .live,body[data-phase="running"] .live,body[data-phase="update"] .live{background:var(--accent);
  animation:pulse 1.4s infinite}
.mini{background:transparent;border:0;color:var(--dim2);font-family:var(--fm);font-size:10px;
  cursor:pointer;padding:2px 0;letter-spacing:.08em}
.mini:hover{color:var(--accent)}
.log{flex:1;overflow:auto;padding:8px 0;font-family:var(--fm);font-size:11.5px;line-height:1.72}
.ln{display:grid;grid-template-columns:58px 42px 1fr;gap:10px;padding:1px 15px;
  animation:slidein .22s ease both}
.ln .t{color:#66736a}
.ln .lv{font-size:9.5px;letter-spacing:.1em;color:var(--dim2);padding-top:2px}
.ln .m{color:#c3cec6;white-space:pre-wrap;word-break:break-all}
.ln[data-lv="cmd"] .lv{color:var(--blue)}
.ln[data-lv="cmd"] .m{color:#b9cbbf}
.ln.app{grid-template-columns:1fr}
.ln.app .m{color:#b9c6d1}
.ln[data-lv="net"] .lv{color:var(--blue)}
.ln[data-lv="ok"] .lv,.ln[data-lv="ok"] .m{color:var(--mint)}
.ln[data-lv="warn"] .lv,.ln[data-lv="warn"] .m{color:var(--warn)}
.ln[data-lv="err"] .lv,.ln[data-lv="err"] .m{color:var(--red)}
.ln[data-lv="sys"] .m{color:var(--dim)}
.empty{position:absolute;inset:41px 0 0;display:flex;align-items:center;justify-content:center;
  font-family:var(--fm);font-size:11px;color:var(--dim2);letter-spacing:.06em;pointer-events:none}
.empty.hide{display:none}
/* scrollbar */
.log::-webkit-scrollbar,.steps::-webkit-scrollbar{width:8px}
.log::-webkit-scrollbar-thumb,.steps::-webkit-scrollbar-thumb{background:#2a3236;border:2px solid var(--panel)}
.log::-webkit-scrollbar-track,.steps::-webkit-scrollbar-track{background:transparent}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.42}}
@keyframes sheen{0%{transform:translateX(-100px)}100%{transform:translateX(700px)}}
@keyframes slidein{from{opacity:0;transform:translateY(3px)}to{opacity:1;transform:none}}
@keyframes pop{from{opacity:0;transform:translateY(6px) scale(.99)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
@media (max-width:1080px){
  body{overflow:auto}
  .shell{height:auto;min-height:100vh;padding:16px}
  main{grid-template-columns:1fr}
  .rail{order:2;max-height:none}
  .facts{grid-template-columns:repeat(3,1fr)}
  h1{font-size:44px}
}
@media (max-height:780px) and (min-width:1081px){
  h1{font-size:46px}
  .hero{padding:18px 22px 16px}
  .desc{min-height:0}
  .console{min-height:120px}
}
</style>
</head>
<body data-phase="idle">
<div class="grid" aria-hidden="true"></div>
<div class="shell">
  <header class="top">
    <div class="brand">
      <svg class="kiwi" viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="11.8" r="9.6" fill="#8b5a34"/>
        <circle cx="12" cy="11.8" r="7.9" fill="#b2eda6"/>
        <circle cx="12" cy="11.8" r="1.9" fill="#f7fbf2"/>
        <g fill="#eaf7e0">
          <ellipse cx="12" cy="7.4" rx=".55" ry="1.05"/>
          <ellipse cx="12" cy="16.2" rx=".55" ry="1.05"/>
          <ellipse cx="7.6" cy="11.8" rx="1.05" ry=".55"/>
          <ellipse cx="16.4" cy="11.8" rx="1.05" ry=".55"/>
          <ellipse cx="8.9" cy="8.7" rx=".8" ry=".5" transform="rotate(-45 8.9 8.7)"/>
          <ellipse cx="15.1" cy="8.7" rx=".8" ry=".5" transform="rotate(45 15.1 8.7)"/>
          <ellipse cx="8.9" cy="14.9" rx=".8" ry=".5" transform="rotate(45 8.9 14.9)"/>
          <ellipse cx="15.1" cy="14.9" rx=".8" ry=".5" transform="rotate(-45 15.1 14.9)"/>
        </g>
      </svg>
      <span class="name">SLLKGUI</span>
    </div>
    <div class="top-right">
      <span class="saved" id="saved">已保存</span>
      <span class="saved" id="modeMsg"></span>
      <span class="mirror-label">模式</span>
      <div class="mirror mode" id="mode" data-m="run" role="group" aria-label="运行模式">
        <span class="thumb" aria-hidden="true"></span>
        <button type="button" data-md="run" class="on">正式</button>
        <button type="button" data-md="gallery">预览</button>
      </div>
      <span class="mirror-label">镜像源</span>
      <div class="mirror" id="mirror" data-m="cn" role="group" aria-label="镜像源">
        <span class="thumb" aria-hidden="true"></span>
        <button type="button" data-m="cn" class="on">国内镜像</button>
        <button type="button" data-m="global">官方源</button>
      </div>
    </div>
  </header>

  <main>
    <aside class="panel rail">
      <div class="panel-head"><span>初始化链路</span><span class="count" id="railCount">0 / 6</span></div>
      <ol class="steps" id="steps"></ol>
    </aside>

    <section class="stage">
      <div class="panel hero">
        <h1 id="word">检测中</h1>
        <p class="desc" id="desc">正在读取本机环境…</p>
        <div class="actions">
          <button type="button" class="btn primary" id="primary"><span id="primaryText">开始初始化</span>
            <svg class="arw" viewBox="0 0 16 16" aria-hidden="true"><path d="M2 8h11M9 4l4 4-4 4"/></svg>
          </button>
          <button type="button" class="btn ghost" id="ghostLogs">打开日志目录</button>
          <button type="button" class="btn ghost" id="ghostExit">退出启动器</button>
        </div>
        <div class="progress" id="progress" hidden>
          <div class="ptrack"><i id="pbar"></i></div>
          <div class="pmeta"><span id="pstage">准备中</span><span id="ptime">00:00</span></div>
        </div>
      </div>

      <div class="facts" id="facts"></div>

      <div class="panel version" id="versionBar">
        <div class="v-info">
          <span class="v-k">版本</span>
          <span class="v-ref" id="vRef">—</span>
          <span class="v-sha" id="vSha"></span>
          <span class="v-flag" id="vFlag" hidden></span>
        </div>
        <div class="v-right">
          <span class="v-latest" id="vLatest"></span>
          <button type="button" class="v-open" id="vOpen">选择版本</button>
        </div>
      </div>

      <div class="panel console">
        <div class="panel-head">
          <span><span id="logTitle">实时日志</span><i class="live" aria-hidden="true"></i></span>
          <span class="chead-right"><span id="logCount">0</span><button type="button" class="mini" id="clearLog">清空</button></span>
        </div>
        <div class="log" id="log" role="log" aria-live="polite"></div>
        <div class="empty" id="logEmpty">等待开始 · 初始化日志将在此实时输出</div>
      </div>
    </section>
  </main>
</div>

<div class="modal" id="vModal" hidden>
  <div class="modal-mask" id="vMask"></div>
  <div class="modal-card" role="dialog" aria-modal="true" aria-labelledby="vTitle">
    <header class="m-head">
      <span class="m-title" id="vTitle">更新基座代码</span>
      <button type="button" class="m-close" id="vClose" aria-label="关闭">×</button>
    </header>
    <div class="m-body">
      <div class="m-meta">
        <span class="m-repo" id="vRepo">—</span>
        <button type="button" class="m-refresh" id="vRefresh">刷新列表</button>
      </div>
      <div class="m-current" id="vCurrent">当前版本 —</div>
      <div class="m-list" id="vList"></div>
      <div class="m-note" id="vNote" hidden></div>
    </div>
    <footer class="m-foot">
      <button type="button" class="btn ghost" id="vCancel">取消</button>
      <button type="button" class="btn primary" id="vApply" disabled>更新到所选版本</button>
    </footer>
  </div>
</div>

<script>
(function(){
  'use strict';
  var TOKEN = '__TOKEN__';
  var el = function(id){ return document.getElementById(id); };
  var state = null, cursor = 0, lvlCount = 0;
  var lastPhase = '', versions = null, vSelected = '', vBusy = false;
  var stepSig = '', factSig = '', polling = null, tickFails = 0;

  var WORD = {
    idle:  ['未就绪', '将安装 uv、CPython、Git，拉取基座源码并创建虚拟环境。'],
    setup: ['初始化中', '正在执行初始化，请保持窗口打开。'],
    update:['更新中', '正在切换代码并同步依赖…'],
    done:  ['已就绪', '可打开基座，或退出启动器。'],
    error: ['初始化中断', '请查看日志后重试。'],
    running:['运行中', '基座运行中。']
  };
  var ACT = {
    idle:  { text: '开始初始化', act: 'setup' },
    setup: { text: '停止初始化', act: 'stop' },
    update:{ text: '停止更新',   act: 'stopUpdate' },
    error: { text: '重试初始化', act: 'setup' },
    done:  { text: '打开基座',   act: 'launch' },
    running:{ text: '退出启动器', act: 'exit' }
  };
  var LVL = { sys:'SYS', cmd:'CMD', out:'OUT', net:'NET', ok:'OK', warn:'WARN', err:'ERR' };

  var SID = Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
  function withSid(path){
    return path + (path.indexOf('?') >= 0 ? '&' : '?') + 'sid=' + SID;
  }
  function api(path, body, method){
    var opt = { headers: { 'X-Token': TOKEN } };
    if(body !== undefined){
      opt.method = method || 'POST';
      opt.headers['Content-Type'] = 'application/json';
      opt.body = JSON.stringify(body);
    }
    return fetch(withSid(path), opt).then(function(r){
      return r.json().catch(function(){ return { ok:false, error:'bad response' }; });
    });
  }
  function esc(s){
    return String(s == null ? '' : s).replace(/[&<>"]/g, function(c){
      return { '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;' }[c];
    });
  }
  function mmss(n){
    n = Math.max(0, n|0);
    var m = Math.floor(n / 60), s = n % 60;
    return (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
  }
  function setMirror(m){
    var box = el('mirror');
    box.dataset.m = m;
    Array.prototype.forEach.call(box.querySelectorAll('button'), function(b){
      b.classList.toggle('on', b.dataset.m === m);
    });
  }
  function setMode(m){
    var box = el('mode');
    box.dataset.m = (m === 'gallery') ? 'gallery' : 'run';
    Array.prototype.forEach.call(box.querySelectorAll('button'), function(b){
      b.classList.toggle('on', b.dataset.md === box.dataset.m);
    });
  }
  function flashMode(text, bad){
    var s = el('modeMsg');
    s.textContent = text;
    s.className = 'saved show' + (bad ? ' bad' : '');
    setTimeout(function(){ s.className = 'saved'; }, 1600);
  }
  function flashSaved(){
    var s = el('saved');
    s.classList.add('show');
    setTimeout(function(){ s.classList.remove('show'); }, 1400);
  }

  function renderVersionBar(s){
    var v = s.version || {};
    el('vRef').textContent = v.ref || (s.ready ? '未知' : '未拉取');
    el('vSha').textContent = v.sha ? ('· ' + v.sha) : '';
    var flag = el('vFlag');
    if(v.ref === 'main'){
      flag.hidden = false;
      flag.className = 'v-flag warn';
      flag.textContent = 'DEV';
    } else if(v.updateAvailable){
      flag.hidden = false;
      flag.className = 'v-flag new';
      flag.textContent = '可更新';
    } else {
      flag.hidden = true;
      flag.textContent = '';
    }
    el('vLatest').textContent = v.latest ? ('最新 ' + v.latest) : '';
    el('vOpen').disabled = (s.phase === 'setup' || s.phase === 'update');
  }

  function openVersions(){
    el('vModal').hidden = false;
    el('vRepo').textContent = (state && state.repo) || '';
    el('vNote').hidden = true;
    if(versions){ renderVersionList(versions); }
    loadVersions(!versions);
    setTimeout(function(){ el('vClose').focus(); }, 30);
  }

  function closeVersions(){
    el('vModal').hidden = true;
  }

  function loadVersions(force){
    if(!el('vList').childElementCount || force){
      el('vList').innerHTML = '<div class="busy">正在读取版本…</div>';
    }
    api('/api/versions' + (force ? '?refresh=1' : '')).then(function(v){
      versions = v;
      renderVersionList(v);
      tickState();
    }).catch(function(){
      el('vList').innerHTML = '<div class="busy">版本列表读取失败</div>';
    });
  }

  function updateBlockReason(){
    if(!state) return '';
    if(state.running) return '基座正在运行，请先关闭基座再更新。';
    if(state.phase === 'setup') return '初始化进行中，完成后再更新。';
    if(state.phase === 'update') return '正在更新，请稍候。';
    return '';
  }

  function renderVersionList(v){
    var cur = v.current || '';
    var exists = false;
    (v.versions || []).forEach(function(x){ if(x.ref === vSelected){ exists = true; } });
    if(!vSelected || !exists){ vSelected = cur; }
    el('vCurrent').textContent = '当前版本 ' + (cur || '未知') + (v.short ? ' · ' + v.short : '');
    if(v.error){
      el('vList').innerHTML = '<div class="busy">' + esc(v.error) + '</div>';
      el('vApply').disabled = true;
      return;
    }
    var rows = (v.versions || []).map(function(item){
      var chips = '';
      if(item.current){ chips += '<span class="chip cur">当前</span>'; }
      if(item.latest){ chips += '<span class="chip latest">最新</span>'; }
      var dev = item.dev ? '<em class="vdev">dev</em>' : '';
      return '<button type="button" class="vrow" data-ref="' + esc(item.ref) + '" aria-pressed="' + (item.ref === vSelected) + '">' +
        '<span class="radio"></span>' +
        '<span class="vlabel"><span>' + esc(item.label) + '</span>' + dev +
        '<span class="vsha2">' + esc(item.short) + '</span></span>' +
        '<span class="vchips">' + chips + '</span></button>';
    }).join('');
    el('vList').innerHTML = rows || '<div class="busy">仓库暂无可选版本</div>';
    Array.prototype.forEach.call(el('vList').querySelectorAll('.vrow'), function(row){
      row.addEventListener('click', function(){
        vSelected = row.dataset.ref;
        renderVersionList(v);
      });
    });
    var blocked = updateBlockReason();
    var note = el('vNote');
    if(blocked){
      note.hidden = false;
      note.textContent = blocked;
    } else if(vSelected === 'main'){
      note.hidden = false;
      note.textContent = 'main 为开发分支，内容随时变化，可能不稳定；需要稳定版本请选择 tag。';
    } else {
      note.hidden = true;
      note.textContent = '';
    }
    el('vApply').disabled = (vBusy || !vSelected || vSelected === cur || !!blocked);
  }

  function applyUpdate(){
    if(!vSelected || vBusy){ return; }
    vBusy = true;
    el('vApply').disabled = true;
    api('/api/update', { ref: vSelected }).then(function(r){
      vBusy = false;
      if(r && r.ok){
        closeVersions();
        tickState();
        tickLogs();
      } else {
        el('vNote').hidden = false;
        el('vNote').textContent = (r && r.error) || '更新失败';
        el('vApply').disabled = false;
      }
    }).catch(function(){
      vBusy = false;
      el('vApply').disabled = false;
    });
  }

  function render(s){
    state = s;
    document.body.dataset.phase = s.phase;
    var w = WORD[s.phase] || WORD.idle;
    el('word').textContent = w[0];
    if(s.phase === 'running'){
      el('desc').textContent = s.owned
        ? ('基座运行中 · ' + (s.modeLabel || '正式模式') + ' · PID ' + s.pid + '，下方为基座日志。')
        : ('检测到其他目录的基座实例 · PID ' + s.pid + '，无法读取其日志。');
    } else if(s.phase === 'update'){
      var target = (s.update && s.update.ref) ? s.update.ref : '所选版本';
      el('desc').textContent = '正在更新到 ' + target + '，过程日志见下方。';
    } else if(s.error){
      el('desc').textContent = s.error;
    } else {
      el('desc').textContent = w[1];
    }

    var a = ACT[s.phase] || ACT.idle;
    el('primaryText').textContent = a.text;
    el('primary').dataset.act = a.act;
    el('primary').hidden = (s.phase === 'running');

    setMirror(s.mirror);
    setMode(s.mode);
    Array.prototype.forEach.call(el('mode').querySelectorAll('button'), function(b){
      b.disabled = s.running;
    });
    el('mode').title = s.running ? '基座运行中，不能切换模式' : '';
    el('railCount').textContent = s.progress + ' / ' + s.total;
    el('logCount').textContent = lvlCount;
    el('logTitle').textContent = (s.phase === 'running') ? '基座日志' : '实时日志';
    el('logEmpty').textContent = (s.phase === 'running' && !s.owned)
      ? '外部基座实例，日志不可用'
      : '等待开始 · 初始化日志将在此实时输出';
    renderVersionBar(s);

    var sig = JSON.stringify(s.steps);
    if(sig !== stepSig){
      stepSig = sig;
      el('steps').innerHTML = s.steps.map(function(st, i){
        return '<li class="step" data-s="' + st.state + '">' +
          '<span class="dot"></span>' +
          '<span class="idx">' + (i < 9 ? '0' : '') + (i + 1) + '</span>' +
          '<span class="lbl">' + esc(st.label) + '</span>' +
          '<span class="note">' + esc(st.note) + '</span></li>';
      }).join('');
    }

    var fsig = s.steps.map(function(x){ return x.state + '|' + x.note; }).join('~');
    if(fsig !== factSig){
      factSig = fsig;
      el('facts').innerHTML = s.steps.map(function(st){
        return '<div class="fact" data-s="' + st.state + '">' +
          '<span class="fk">' + esc(st.short) + '</span>' +
          '<span class="fv">' + esc(st.note) + '</span></div>';
      }).join('');
    }

    var showProgress = (s.phase === 'setup' || s.phase === 'update' || (s.phase === 'done' && !s.running) || s.phase === 'error');
    el('progress').hidden = !showProgress;
    if(showProgress){
      var pct = Math.round((s.progress / s.total) * 100);
      if(s.phase === 'setup' && s.current){
        var cur = s.steps.filter(function(x){ return x.id === s.current; })[0];
        el('pstage').textContent = '正在执行 · ' + (cur ? cur.label : s.current);
      } else if(s.phase === 'update'){
        el('pstage').textContent = '正在更新 · ' + ((s.update && s.update.ref) || '');
      } else if(s.phase === 'error'){
        el('pstage').textContent = '已中断';
      } else {
        el('pstage').textContent = s.progress + ' / ' + s.total + ' 项组件就绪';
      }
      el('pbar').style.width = (s.phase === 'update' ? 100 : (s.phase === 'setup' ? Math.max(pct, 4) : pct)) + '%';
      el('ptime').textContent = mmss(s.elapsed);
    }

    if(lastPhase === 'update' && s.phase !== 'update'){ loadVersions(false); }
    lastPhase = s.phase;
  }

  function addLine(l){
    var box = el('log');
    var near = box.scrollHeight - box.scrollTop - box.clientHeight < 60;
    var row = document.createElement('div');
    row.className = 'ln';
    row.dataset.lv = l.level;
    var t = document.createElement('span'); t.className = 't'; t.textContent = l.t;
    var v = document.createElement('span'); v.className = 'lv'; v.textContent = LVL[l.level] || l.level.toUpperCase();
    var m = document.createElement('span'); m.className = 'm'; m.textContent = l.text;
    row.appendChild(t); row.appendChild(v); row.appendChild(m);
    box.appendChild(row);
    lvlCount++;
    while(box.childElementCount > 700){ box.removeChild(box.firstChild); }
    if(near){ box.scrollTop = box.scrollHeight; }
    el('logCount').textContent = lvlCount;
    el('logEmpty').classList.add('hide');
  }

  function addAppLine(text){
    var box = el('log');
    var near = box.scrollHeight - box.scrollTop - box.clientHeight < 80;
    var row = document.createElement('div');
    row.className = 'ln app';
    var m = document.createElement('span');
    m.className = 'm';
    m.textContent = text;
    row.appendChild(m);
    box.appendChild(row);
    while(box.childElementCount > 900){ box.removeChild(box.firstChild); }
    if(near){ box.scrollTop = box.scrollHeight; }
  }

  function tickState(){
    api('/api/state').then(function(s){
      if(!s || !s.phase){ throw new Error('stale session'); }
      tickFails = 0;
      render(s);
      document.title = 'SllkGui 启动器 · ' + ((WORD[s.phase] || WORD.idle)[0]);
    }).catch(function(){
      tickFails++;
      if(tickFails < 3){ return; }
      document.body.dataset.phase = 'off';
      el('word').textContent = '连接中断';
      el('desc').textContent = '启动器服务已关闭，可重新运行启动器。';
      el('primary').hidden = true;
      if(polling){ clearInterval(polling); polling = null; }
    });
  }

  var appLogSig = '', logMode = '';

  function tickAppLog(){
    api('/api/applog').then(function(r){
      if(!r || !r.lines) return;
      var sig = r.lines.join('\n');
      if(sig === appLogSig) return;
      appLogSig = sig;
      var box = el('log');
      box.innerHTML = '';
      r.lines.forEach(addAppLine);
      lvlCount = r.lines.length;
      el('logCount').textContent = lvlCount;
      if(r.lines.length > 0){ el('logEmpty').classList.add('hide'); }
      box.scrollTop = box.scrollHeight;
    }).catch(function(){});
  }

  function tickLogs(){
    var mode = (state && state.phase === 'running' && state.owned) ? 'app' : 'launcher';
    if(mode !== logMode){
      logMode = mode;
      appLogSig = '';
      el('log').innerHTML = '';
      lvlCount = 0;
      el('logCount').textContent = '0';
      el('logEmpty').classList.remove('hide');
    }
    if(mode === 'app'){ tickAppLog(); return; }
    api('/api/log?cursor=' + cursor).then(function(r){
      if(!r || !r.lines) return;
      cursor = r.cursor;
      r.lines.forEach(addLine);
    }).catch(function(){});
  }

  function shutdownUi(){
    document.body.dataset.phase = 'off';
    el('word').textContent = '启动器已退出';
    el('desc').textContent = '可以关闭此页面。';
    el('primary').hidden = true;
    if(polling){ clearInterval(polling); polling = null; }
    try { window.close(); } catch(e){}
  }
  function exitLauncher(){
    api('/api/exit', {}).then(function(r){
      if(r && r.ok === false){ el('desc').textContent = r.error || '暂时无法退出'; return; }
      shutdownUi();
    }).catch(shutdownUi);
  }

  function boot(){
    el('primary').addEventListener('click', function(){
      var act = this.dataset.act;
      if(act === 'setup'){
        this.disabled = true;
        api('/api/setup', {}).then(function(r){
          if(r && r.ok === false && r.error === 'busy'){ el('desc').textContent = '初始化正在进行中。'; }
          setTimeout(function(){ el('primary').disabled = false; }, 600);
          tickState();
        }).catch(function(){ el('primary').disabled = false; });
      } else if(act === 'stop'){
        api('/api/setup/stop', {}).then(tickState);
      } else if(act === 'stopUpdate'){
        api('/api/update/stop', {}).then(tickState);
      } else if(act === 'launch'){
        api('/api/launch', {}).then(function(r){
          if(r && r.ok){ setTimeout(tickState, 600); }
          else if(r){ el('desc').textContent = '启动失败：' + r.error; }
        });
      } else if(act === 'exit'){
        exitLauncher();
      }
    });
    el('vOpen').addEventListener('click', openVersions);
    el('vClose').addEventListener('click', closeVersions);
    el('vCancel').addEventListener('click', closeVersions);
    el('vMask').addEventListener('click', closeVersions);
    el('vApply').addEventListener('click', applyUpdate);
    el('vRefresh').addEventListener('click', function(){ loadVersions(true); });
    document.addEventListener('keydown', function(e){
      if(e.key === 'Escape' && !el('vModal').hidden){ closeVersions(); }
    });
    el('ghostLogs').addEventListener('click', function(){ api('/api/open', {}).catch(function(){}); });
    el('ghostExit').addEventListener('click', exitLauncher);
    el('clearLog').addEventListener('click', function(){
      el('log').innerHTML = '';
      lvlCount = 0;
      el('logCount').textContent = '0';
      el('logEmpty').classList.remove('hide');
    });
    Array.prototype.forEach.call(document.querySelectorAll('#mirror button'), function(b){
      b.addEventListener('click', function(){
        if(state && state.phase === 'setup') return;
        var m = b.dataset.m;
        setMirror(m);
        api('/api/config', { mirror: m }).then(function(s){
          if(s && s.mirror){ setMirror(s.mirror); }
          flashSaved();
        }).catch(function(){});
      });
    });
    Array.prototype.forEach.call(document.querySelectorAll('#mode button'), function(b){
      b.addEventListener('click', function(){
        if(state && state.running){ flashMode('运行中不可切换', true); return; }
        var m = b.dataset.md;
        setMode(m);
        api('/api/mode', { mode: m }).then(function(r){
          if(r && r.ok){ flashMode('已切换'); tickState(); }
          else {
            setMode(state ? state.mode : 'run');
            flashMode((r && r.error) || '切换失败', true);
          }
        }).catch(function(){
          setMode(state ? state.mode : 'run');
          flashMode('切换失败', true);
        });
      });
    });
    tickState();
    tickLogs();
    polling = setInterval(function(){
      tickState();
      tickLogs();
    }, 800);
    window.addEventListener('pagehide', function(){
      try { fetch(withSid('/api/bye'), { method: 'POST', headers: { 'X-Token': TOKEN }, keepalive: true }); } catch (e) { }
    });
  }

  boot();
})();
</script>
</body>
</html>
'@

# ---------------------------------------------------------------------------
# 已有实例：直接复用其页面，不再重复初始化
# ---------------------------------------------------------------------------
if(-not $IsPrimary){
  $portFile = Join-Path $Runtime 'port.txt'
  $p = ''
  for($i = 0; $i -lt 12; $i++){
    if(Test-Path -LiteralPath $portFile){
      try { $p = ([string](Get-Content -LiteralPath $portFile -Raw)).Trim() } catch { $p = '' }
      if($p -match '^\d+$'){ break }
    }
    Start-Sleep -Milliseconds 250
  }
  $alive = $false
  if($p -match '^\d+$'){
    try {
      $tc = New-Object System.Net.Sockets.TcpClient
      $ar = $tc.BeginConnect('127.0.0.1', [int]$p, $null, $null)
      if($ar.AsyncWaitHandle.WaitOne(400)){ $alive = $tc.Connected }
      $tc.Close()
    } catch { }
  }
  if($alive){
    $handled = $false
    try {
      $page = (Invoke-WebRequest -Uri ('http://127.0.0.1:' + $p + '/') -UseBasicParsing -TimeoutSec 3).Content
      $t = [regex]::Match($page, "TOKEN = '([a-f0-9]+)'").Groups[1].Value
      if($t){
        $hdrs = @{ 'X-Token' = $t }
        $s = Invoke-RestMethod -Uri ('http://127.0.0.1:' + $p + '/api/state') -Headers $hdrs -TimeoutSec 3
        if($s.ready -and -not $s.running){
          [void](Invoke-RestMethod -Uri ('http://127.0.0.1:' + $p + '/api/launch') -Method Post -Headers @{ 'X-Token' = $t; 'Content-Type' = 'application/json' } -Body '{}' -TimeoutSec 15)
          $handled = $true
        }
      }
    } catch { }
    if(-not $handled){
      $url = 'http://127.0.0.1:' + $p + '/'
      if(-not (Open-Page $url)){ Show-Dialog ('无法调用系统浏览器，请手动打开：' + $url) 'SllkGui 启动器' 'Warning' }
    }
    exit
  }
  Show-Dialog '已有启动器实例在运行，但无法连接它的界面（端口信息缺失或已失效）。请关闭其它启动器窗口后重试。' 'SllkGui 启动器' 'Warning'
  exit
}

# ---------------------------------------------------------------------------
# 快速通道：环境已就绪则直接启动基座，不创建端口、不打开网页
# ---------------------------------------------------------------------------
$fastState = Get-State $true
$fastBase = Get-BaseProcess
if($fastState.ready -and $fastBase.pid -eq 0){
  $fastLaunch = Start-BaseApp
  if($fastLaunch.ok){ exit }
  $Shared.error = '启动失败：' + $fastLaunch.error
  $Shared.phase = 'done'
}

# ---------------------------------------------------------------------------
# 启动本地服务
# ---------------------------------------------------------------------------
$Listener = $null
$script:Port = 0
for($p = 17823; $p -le 17860; $p++){
  try {
    $l = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $p)
    $l.Start()
    $Listener = $l
    $script:Port = $p
    break
  } catch { }
}
if(-not $Listener){
  Show-Dialog '无法绑定本地端口（17823-17860 均被占用），启动器无法打开界面。' 'SllkGui 启动器' 'Error'
  exit 1
}
try { [IO.File]::WriteAllText((Join-Path $Runtime 'port.txt'), [string]$script:Port) } catch { }

[void](Get-State $true)
Add-Content -LiteralPath (Join-Path $LogDir 'launcher.log') -Value ((Get-Date).ToString('yyyy-MM-dd HH:mm:ss') + ' launcher started on port ' + $script:Port) -Encoding UTF8

$pageUrl = 'http://127.0.0.1:' + $script:Port + '/'
if(-not (Open-Page $pageUrl)){ Show-Dialog ('无法调用系统浏览器，请手动打开：' + $pageUrl) 'SllkGui 启动器' 'Warning' }

$lastRequest = Get-Date
$script:LastDrain = Get-Date
while(-not $script:Shutdown){
  try {
    if($Listener.Pending()){
      $client = $Listener.AcceptTcpClient()
      try {
        $client.ReceiveTimeout = 5000
        $client.SendTimeout = 5000
        $stream = $client.GetStream()
        $req = Read-Request $stream
        if($req){
          $lastRequest = Get-Date
          Handle-Request $stream $req
        }
      } catch { } finally { try { $client.Close() } catch { } }
    } else {
      Start-Sleep -Milliseconds 70
    }
    Complete-PipelineIfDone
    Complete-UpdateIfDone
    if(((Get-Date) - $script:LastDrain).TotalSeconds -gt 2){ $script:LastDrain = Get-Date; Drain-Queue }
    if($script:ByeAt -and $Shared.phase -ne 'setup' -and $Shared.phase -ne 'update' -and ((Get-Date) - $script:ByeAt).TotalSeconds -gt 3){ $script:ExitReason = 'page-closed'; break }
    if($Shared.phase -ne 'setup' -and $Shared.phase -ne 'update' -and ((Get-Date) - $lastRequest).TotalSeconds -gt 600){ $script:ExitReason = 'idle'; break }
  } catch {
    Start-Sleep -Milliseconds 120
  }
}
if($script:Shutdown){ $script:ExitReason = 'user-exit' }
try { Add-Content -LiteralPath (Join-Path $LogDir 'launcher.log') -Value ((Get-Date).ToString('yyyy-MM-dd HH:mm:ss') + ' launcher exit: ' + $script:ExitReason) -Encoding UTF8 } catch { }
try { $Listener.Stop() } catch { }
try { Remove-Item -LiteralPath (Join-Path $Runtime 'port.txt') -Force } catch { }
try { $Mutex.ReleaseMutex() } catch { }
