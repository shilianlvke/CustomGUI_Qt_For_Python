using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;

namespace SllkGui.Launcher
{
    internal sealed class RefInfo
    {
        public string Name = "";
        public string Sha = "";
        public bool IsMain;
    }

    internal sealed class Bootstrap
    {
        private readonly LauncherPaths _paths;
        private readonly Config _config;
        private readonly Manifest _manifest;
        private readonly EnvManager _env;
        private readonly Toolchain _tools;
        private readonly LogBuffer _log;
        private readonly LauncherState _state;
        private readonly Downloader _downloader;
        private readonly object _taskLock = new object();
        private CancellationTokenSource _cts;
        private Task _task;
        private string _buildingDir;

        public Bootstrap(LauncherPaths paths, Config config, Manifest manifest, EnvManager env, Toolchain tools, LogBuffer log, LauncherState state)
        {
            _paths = paths;
            _config = config;
            _manifest = manifest;
            _env = env;
            _tools = tools;
            _log = log;
            _state = state;
            _downloader = new Downloader(paths, log, delegate(DownloadProgress p)
            {
                lock (_state.Lock)
                {
                    _state.Download.Active = p.Active;
                    _state.Download.Label = p.Label;
                    _state.Download.Received = p.Received;
                    _state.Download.Total = p.Total;
                    _state.Download.Percent = p.Percent;
                    _state.Download.Text = p.Text;
                }
            });
        }

        public bool Busy
        {
            get
            {
                lock (_taskLock) return _task != null && !_task.IsCompleted;
            }
        }

        public void StartSetup(string profileName, string mirror)
        {
            lock (_taskLock)
            {
                if (Busy) throw new InvalidOperationException("已有初始化或更新任务在运行");
                ProfileInfo profile = _manifest.Profile(profileName);
                _config.Profile = profile.Name;
                if (mirror == "cn" || mirror == "global") _config.Mirror = mirror;
                _config.Save(_paths.ConfigPath);
                _state.Reset("setup");
                _state.Phase = "setup";
                _log.Sys("开始初始化 · 配置 " + profile.Label + " · 镜像 " + _manifest.Mirror(_config.Mirror).Label);
                _cts = new CancellationTokenSource();
                CancellationToken ct = _cts.Token;
                _task = Task.Run(delegate { RunSetup(profile, ct); });
            }
        }

        public void StartUpdate(string refName, bool forceSame)
        {
            lock (_taskLock)
            {
                if (Busy) throw new InvalidOperationException("已有初始化或更新任务在运行");
                if (_env.Current == null) throw new InvalidOperationException("尚未初始化环境");
                if (!_manifest.Profile(_config.Profile).UseGit || !string.Equals(_env.Current.SourceKind, "git", StringComparison.OrdinalIgnoreCase))
                    throw new InvalidOperationException("当前为轻量安装，不支持版本切换；请重新初始化并选择标准或完整配置");
                _state.Reset("update");
                _state.Phase = "update";
                _state.UpdateRef = refName ?? "";
                _log.Sys("开始更新到 " + (string.IsNullOrEmpty(refName) ? "main" : refName) + " · 新环境构建期间当前环境保持不变");
                _cts = new CancellationTokenSource();
                CancellationToken ct = _cts.Token;
                _task = Task.Run(delegate { RunUpdate(refName, forceSame, ct); });
            }
        }

        public void StartRepair()
        {
            lock (_taskLock)
            {
                if (Busy) throw new InvalidOperationException("已有初始化或更新任务在运行");
                EnvRecord current = _env.Current;
                if (current == null) throw new InvalidOperationException("尚未初始化环境");
                _state.Reset("update");
                _state.Phase = "update";
                _state.UpdateRef = current.Ref;
                _log.Sys("修复环境：从 " + current.Ref + " 构建新的独立环境，成功后再切换");
                _cts = new CancellationTokenSource();
                CancellationToken ct = _cts.Token;
                _task = Task.Run(delegate { RunRepair(current, ct); });
            }
        }

        public void Cancel()
        {
            lock (_taskLock)
            {
                if (!Busy) return;
                _state.Cancel = true;
                try { _cts.Cancel(); } catch { }
                _log.Warn("已请求取消当前任务");
            }
        }

        private void RunSetup(ProfileInfo profile, CancellationToken ct)
        {
            EnvRecord built = null;
            try
            {
                built = BuildEnv(null, profile, ct);
                _env.SetCurrent(built);
                lock (_state.Lock)
                {
                    _state.Phase = "done";
                    _state.Error = "";
                    _state.FinishedAt = DateTime.Now;
                    _state.Current = "";
                }
                _log.Ok("初始化完成 · " + built.Ref + " · " + built.Profile);
            }
            catch (OperationCanceledException)
            {
                Fail("已取消初始化", built);
            }
            catch (Exception ex)
            {
                Fail(ex.Message, built);
            }
        }

        private void RunUpdate(string refName, bool forceSame, CancellationToken ct)
        {
            EnvRecord built = null;
            EnvRecord old = _env.Current;
            try
            {
                ProfileInfo profile = _manifest.Profile(_config.Profile);
                RefInfo target = ResolveRef(string.IsNullOrEmpty(refName) ? "main" : refName, ct);
                if (!forceSame && old != null && string.Equals(old.Sha, target.Sha, StringComparison.OrdinalIgnoreCase))
                {
                    lock (_state.Lock)
                    {
                        _state.Phase = "done";
                        _state.FinishedAt = DateTime.Now;
                        _state.SyncSummary = new Dictionary<string, object>
                        {
                            { "ref", target.Name }, { "from", old.Sha }, { "to", target.Sha },
                            { "changed", false }, { "discarded", 0 }, { "forced", false }
                        };
                    }
                    _log.Ok("已是最新（" + target.Sha.Substring(0, Math.Min(7, target.Sha.Length)) + "），无需更新");
                    return;
                }
                built = BuildEnv(target, profile, ct);
                _env.SetCurrent(built);
                lock (_state.Lock)
                {
                    _state.Phase = "done";
                    _state.Error = "";
                    _state.FinishedAt = DateTime.Now;
                    _state.Current = "";
                    _state.SyncSummary = new Dictionary<string, object>
                    {
                        { "ref", target.Name }, { "from", old == null ? "" : old.Sha }, { "to", target.Sha },
                        { "changed", true }, { "discarded", 0 }, { "forced", false }
                    };
                }
                _log.Ok("已切换到新环境 · " + target.Name + " · " + built.Id);
            }
            catch (OperationCanceledException)
            {
                Fail("已取消更新", built);
            }
            catch (Exception ex)
            {
                Fail(ex.Message, built);
            }
        }

        private void RunRepair(EnvRecord current, CancellationToken ct)
        {
            EnvRecord built = null;
            try
            {
                ProfileInfo profile = _manifest.Profile(_config.Profile);
                RefInfo target;
                if (string.Equals(current.SourceKind, "git", StringComparison.OrdinalIgnoreCase))
                    target = ResolveRef(string.IsNullOrEmpty(current.Ref) ? "main" : current.Ref, ct);
                else
                    target = new RefInfo { Name = current.Ref, Sha = current.Sha };
                built = BuildEnv(target, profile, ct);
                _env.SetCurrent(built);
                lock (_state.Lock)
                {
                    _state.Phase = "done";
                    _state.Error = "";
                    _state.FinishedAt = DateTime.Now;
                    _state.Current = "";
                }
                _log.Ok("环境修复完成 · " + built.Id);
            }
            catch (OperationCanceledException)
            {
                Fail("已取消修复", built);
            }
            catch (Exception ex)
            {
                Fail(ex.Message, built);
            }
        }

        private void Fail(string message, EnvRecord built)
        {
            lock (_state.Lock)
            {
                _state.Phase = "error";
                _state.Error = message;
                _state.FinishedAt = DateTime.Now;
                _state.Current = "";
                _state.Download.Active = false;
                _state.Download.Text = "";
                _state.Download.Percent = 0;
                foreach (string key in _state.Steps.Keys.ToList())
                {
                    StepState s = _state.Steps[key];
                    if (s.State == "active") s.State = "fail";
                }
            }
            _log.Err(message);
            if (built != null && (_env.Current == null || !string.Equals(_env.Current.Id, built.Id, StringComparison.OrdinalIgnoreCase)))
            {
                string dir = Path.Combine(_paths.EnvRoot, built.Id);
                bool isCurrent = _env.Current != null && string.Equals(_env.Current.Id, built.Id, StringComparison.OrdinalIgnoreCase);
                if (!isCurrent && Directory.Exists(dir)) Util.TryDeleteDirectory(dir);
            }
        }

        private EnvRecord BuildEnv(RefInfo target, ProfileInfo profile, CancellationToken ct)
        {
            if (!profile.UseGit)
                throw new InvalidOperationException("当前启动器要求 Git 版本管理；请选择标准或完整配置");
            string envId = "env-" + DateTime.Now.ToString("yyyyMMdd-HHmmss") + "-" + Guid.NewGuid().ToString("N").Substring(0, 4);
            string finalDir = Path.Combine(_paths.EnvRoot, envId);
            string baseDir = Path.Combine(finalDir, "base");
            string venvDir = Path.Combine(baseDir, ".venv");
            _buildingDir = finalDir;
            Directory.CreateDirectory(_paths.EnvRoot);
            if (Directory.Exists(finalDir)) Util.TryDeleteDirectory(finalDir);
            Directory.CreateDirectory(finalDir);

            try
            {
                Step("uv", "active", "检测中");
                string uv = EnsureUv(ct);
                Step("uv", "ok", VersionNote(_tools.UvVersion(), "uv"));

                Step("python", "active", "安装中");
                string python = EnsurePython(ct);
                Step("python", "ok", VersionNote(_tools.FindPython(_config.Python), "CPython"));

                Step("git", "active", "检测中");
                if (profile.UseGit)
                {
                    EnsureGit(ct);
                    Step("git", "ok", VersionNote(_tools.GitVersion(), "Git"));
                }
                else
                {
                    Step("git", "ok", "轻量配置跳过");
                }

                Step("source", "active", "拉取中");
                if (target == null) target = ResolveRef("", ct);
                string sourceKind = "git";
                CloneSource(target, baseDir, ct);
                Step("source", "ok", target.Name + " · " + ShortSha(target.Sha));

                Step("venv", "active", "创建中");
                ProcResult venv = _tools.CreateVenv(baseDir, python, ct).GetAwaiter().GetResult();
                if (venv.Cancelled) throw new OperationCanceledException();
                if (venv.ExitCode != 0) throw new InvalidOperationException("虚拟环境创建失败：" + venv.Tail(5));
                if (!File.Exists(Path.Combine(venvDir, "Scripts", "python.exe")))
                    throw new InvalidOperationException("虚拟环境创建失败：缺少 python.exe");
                Step("venv", "ok", "已创建");

                Step("deps", "active", profile.IncludeAddons ? "同步中（含 Addons）" : "同步中（Essentials）");
                MirrorInfo mirror = _manifest.Mirror(_config.Mirror);
                ProcResult sync = _tools.SyncDeps(baseDir, python, profile, mirror.Pypi, _config.Mirror == "cn", ct).GetAwaiter().GetResult();
                if (sync.Cancelled) throw new OperationCanceledException();
                if (sync.ExitCode != 0) throw new InvalidOperationException("依赖同步失败：" + sync.Tail(8));
                Step("deps", "ok", "已同步");

                Step("verify", "active", "校验中");
                string entry = Path.Combine(venvDir, "Scripts", "sllkgui.exe");
                if (!File.Exists(entry)) throw new InvalidOperationException("安装不完整：缺少 sllkgui.exe 入口");
                ProcResult py = _tools.CheckPySide6(baseDir, venvDir);
                if (py.ExitCode != 0) throw new InvalidOperationException("PySide6 校验失败：" + py.Tail(6));
                string pyVersion = (py.Output.LastOrDefault() ?? "PySide6").Trim();
                Step("verify", "ok", pyVersion);

                EnvRecord record = _env.Create(
                    envId,
                    Path.Combine("envs", envId, "base"),
                    Path.Combine("envs", envId, "base", ".venv"),
                    target.Name,
                    target.Sha,
                    profile.Name,
                    sourceKind,
                    python,
                    _config.Repo);
                _env.WriteMeta(record);
                _buildingDir = null;
                return record;
            }
            catch
            {
                Util.TryDeleteDirectory(finalDir);
                _buildingDir = null;
                throw;
            }
        }

        private string EnsureUv(CancellationToken ct)
        {
            string uv = _tools.ResolveUv();
            if (uv != null)
            {
                string actual = Util.FirstSemver(_tools.UvVersion());
                if (Util.VersionAtLeast(actual, _manifest.Uv.Version)) return uv;
                _log.Warn("PATH 中的 uv 版本为 " + (string.IsNullOrEmpty(actual) ? "未知" : actual) +
                    "，低于固定版本 " + _manifest.Uv.Version + "，将安装固定版本");
            }
            MirrorInfo mirror = _manifest.Mirror(_config.Mirror);
            string arch = _manifest.IsArm64() ? "arm64" : "x64";
            string zip = Path.Combine(_paths.Cache, "uv-" + _manifest.Uv.Version + "-" + arch + ".zip");
            _log.Sys("安装 uv " + _manifest.Uv.Version + "（" + arch + "）");
            bool downloaded = false;
            Exception last = null;
            foreach (string url in _manifest.UvUrls(mirror))
            {
                try
                {
                    _log.Sys("uv 源：" + url);
                    _downloader.DownloadAsync(url, zip, _manifest.UvSha256(), "uv " + _manifest.Uv.Version, _manifest.UvBytes(), ct).GetAwaiter().GetResult();
                    downloaded = true;
                    break;
                }
                catch (OperationCanceledException) { throw; }
                catch (Exception ex)
                {
                    last = ex;
                    _log.Warn("uv 源失败，尝试下一个：" + ex.Message);
                    Util.TryDeleteFile(zip);
                    Util.TryDeleteFile(zip + ".part");
                }
            }
            if (!downloaded) throw new InvalidOperationException("uv 下载失败：" + (last == null ? "未知错误" : last.Message));
            _downloader.ExtractZip(zip, _paths.UvDir);
            _tools.ResetCache();
            uv = _tools.ResolveUv();
            if (uv == null) throw new InvalidOperationException("uv 安装失败：未找到 uv.exe");
            return uv;
        }

        private string EnsurePython(CancellationToken ct)
        {
            // 先探测 uv 可见的已有解释器（继承用户环境的 UV_PYTHON_INSTALL_DIR），
            // 找到就直接复用，不再重复下载。
            string python = _tools.FindPython(_config.Python);
            if (!string.IsNullOrEmpty(python))
            {
                _log.Ok("复用已安装的 CPython " + _config.Python + "：" + python);
                return python;
            }
            // 未找到时才下载，且使用用户在配置中选择的镜像源。
            MirrorInfo mirror = _manifest.Mirror(_config.Mirror);
            _log.Sys("未找到 CPython " + _config.Python + "，使用" + mirror.Label + "安装");
            bool useMirror = _config.Mirror == "cn";
            ProcResult r = _tools.InstallPython(_config.Python, mirror.Python, useMirror, ct).GetAwaiter().GetResult();
            if (r.Cancelled) throw new OperationCanceledException();
            if (r.ExitCode != 0 && useMirror)
            {
                _log.Warn("国内 CPython 镜像失败，回退官方源：" + r.Tail(3));
                r = _tools.InstallPython(_config.Python, mirror.Python, false, ct).GetAwaiter().GetResult();
                if (r.Cancelled) throw new OperationCanceledException();
            }
            if (r.ExitCode != 0) throw new InvalidOperationException("CPython 安装失败：" + r.Tail(8));
            _tools.ResetCache();
            python = _tools.FindPython(_config.Python, true);
            if (string.IsNullOrEmpty(python)) throw new InvalidOperationException("CPython 安装完成但无法定位解释器");
            return python;
        }

        private void EnsureGit(CancellationToken ct)
        {
            if (_tools.ResolveGit() != null) return;
            MirrorInfo mirror = _manifest.Mirror(_config.Mirror);
            string zip = Path.Combine(_paths.Cache, "mingit-" + _manifest.MiniGit.Version + ".zip");
            _log.Sys("安装便携版 Git " + _manifest.MiniGit.Version);
            bool downloaded = false;
            Exception last = null;
            foreach (string url in _manifest.MiniGitUrls(mirror))
            {
                try
                {
                    _log.Sys("Git 源：" + url);
                    _downloader.DownloadAsync(url, zip, _manifest.MiniGit.Sha256, "MinGit " + _manifest.MiniGit.Version, _manifest.MiniGit.Bytes, ct).GetAwaiter().GetResult();
                    downloaded = true;
                    break;
                }
                catch (OperationCanceledException) { throw; }
                catch (Exception ex)
                {
                    last = ex;
                    _log.Warn("Git 源失败，尝试下一个：" + ex.Message);
                    Util.TryDeleteFile(zip);
                    Util.TryDeleteFile(zip + ".part");
                }
            }
            if (!downloaded) throw new InvalidOperationException("Git 下载失败：" + (last == null ? "未知错误" : last.Message));
            _downloader.ExtractZip(zip, _paths.GitDir);
            _tools.ResetCache();
            if (_tools.ResolveGit() == null) throw new InvalidOperationException("Git 安装失败：未找到 git.exe");
        }

        private void CloneSource(RefInfo target, string baseDir, CancellationToken ct)
        {
            string repo = _config.Repo;
            _log.Sys("克隆 " + repo + " · " + target.Name);
            ProcResult r = _tools.GitClone(repo, target.IsMain ? "" : target.Name, baseDir, false, ct).GetAwaiter().GetResult();
            if (r.Cancelled) throw new OperationCanceledException();
            if (r.ExitCode != 0) throw new InvalidOperationException("源码拉取失败：" + r.Tail(8));
            string head = _tools.GitHead(baseDir);
            if (!string.IsNullOrEmpty(target.Sha) && !string.Equals(head, target.Sha, StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("源码校验失败：HEAD " + ShortSha(head) + " 与期望 " + ShortSha(target.Sha) + " 不一致");
            if (!File.Exists(Path.Combine(baseDir, "pyproject.toml")))
                throw new InvalidOperationException("源码不完整：缺少 pyproject.toml");
        }

        private RefInfo ResolveRef(string refName, CancellationToken ct)
        {
            Dictionary<string, string> map = _tools.GitLsRemote(_config.Repo, false, ct).GetAwaiter().GetResult();
            if (string.IsNullOrEmpty(refName) || refName == "latest")
            {
                Dictionary<string, string> tags = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
                foreach (KeyValuePair<string, string> kv in map)
                {
                    string r = kv.Key;
                    if (!r.StartsWith("refs/tags/", StringComparison.Ordinal)) continue;
                    string name = r.Substring("refs/tags/".Length);
                    bool deref = name.EndsWith("^{}", StringComparison.Ordinal);
                    if (deref) name = name.Substring(0, name.Length - 3);
                    if (!name.StartsWith("base-", StringComparison.OrdinalIgnoreCase)) continue;
                    if (deref || !tags.ContainsKey(name)) tags[name] = kv.Value;
                }
                string best = "";
                string bestKey = "";
                foreach (string name in tags.Keys)
                {
                    string key = VersionKey(name);
                    if (key.CompareTo(bestKey) > 0) { bestKey = key; best = name; }
                }
                if (best.Length > 0) return new RefInfo { Name = best, Sha = tags[best], IsMain = false };
                string mainSha;
                if (map.TryGetValue("refs/heads/main", out mainSha))
                    return new RefInfo { Name = "main", Sha = mainSha, IsMain = true };
                throw new InvalidOperationException("远端没有 base-* 版本，也没有 main 分支");
            }
            if (!Config.IsValidBranch(refName)) throw new InvalidOperationException("版本号不合法");
            if (refName == "main")
            {
                string sha;
                if (!map.TryGetValue("refs/heads/main", out sha)) throw new InvalidOperationException("远端不存在 main 分支");
                return new RefInfo { Name = "main", Sha = sha, IsMain = true };
            }
            string tagSha;
            if (map.TryGetValue("refs/tags/" + refName + "^{}", out tagSha))
                return new RefInfo { Name = refName, Sha = tagSha, IsMain = false };
            if (map.TryGetValue("refs/tags/" + refName, out tagSha))
                return new RefInfo { Name = refName, Sha = tagSha, IsMain = false };
            throw new InvalidOperationException("版本不存在或已从仓库删除：" + refName);
        }

        private static string VersionKey(string name)
        {
            int[] parts = new int[] { 0, 0, 0, 0 };
            MatchCollection matches = Regex.Matches(name, "\\d+");
            for (int i = 0; i < matches.Count && i < 4; i++)
            {
                int value;
                if (int.TryParse(matches[i].Value, out value)) parts[i] = value;
            }
            return string.Format("{0:D4}.{1:D4}.{2:D4}.{3:D4}", parts[0], parts[1], parts[2], parts[3]);
        }

        private static string ShortSha(string sha)
        {
            if (string.IsNullOrEmpty(sha)) return "";
            return sha.Length <= 7 ? sha : sha.Substring(0, 7);
        }

        private static string VersionNote(string version, string fallback)
        {
            return string.IsNullOrEmpty(version) ? fallback : version.Trim();
        }

        private void Step(string id, string state, string note)
        {
            if (_state.Cancel) throw new OperationCanceledException();
            _state.SetStep(id, state, note);
        }
    }
}
