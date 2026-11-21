using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace SllkGui.Launcher
{
    internal sealed class ProcResult
    {
        public int ExitCode = -1;
        public bool Cancelled;
        public bool TimedOut;
        public List<string> Output = new List<string>();

        public string Tail(int count)
        {
            if (Output.Count == 0) return "";
            int start = Math.Max(0, Output.Count - count);
            StringBuilder sb = new StringBuilder();
            for (int i = start; i < Output.Count; i++)
            {
                if (sb.Length > 0) sb.AppendLine();
                sb.Append(Output[i]);
            }
            return sb.ToString();
        }
    }

    internal sealed class Toolchain
    {
        private readonly LauncherPaths _paths;
        private readonly Manifest _manifest;
        private readonly LogBuffer _log;
        private readonly object _cacheLock = new object();
        private string _uvCache;
        private string _gitCache;
        private DateTime _uvCacheAt = DateTime.MinValue;
        private DateTime _gitCacheAt = DateTime.MinValue;
        private string _uvVersion;
        private string _gitVersion;
        private DateTime _uvVersionAt = DateTime.MinValue;
        private DateTime _gitVersionAt = DateTime.MinValue;
        private string _pyCacheVersion;
        private string _pyCache;
        private DateTime _pyCacheAt = DateTime.MinValue;

        public Toolchain(LauncherPaths paths, Manifest manifest, LogBuffer log)
        {
            _paths = paths;
            _manifest = manifest;
            _log = log;
            _paths.Ensure();
        }

        public string UvLocal { get { return Path.Combine(_paths.UvDir, "uv.exe"); } }
        public string GitLocal { get { return Path.Combine(_paths.GitDir, "cmd", "git.exe"); } }

        public void ResetCache()
        {
            lock (_cacheLock)
            {
                _uvCacheAt = DateTime.MinValue;
                _gitCacheAt = DateTime.MinValue;
                _uvVersionAt = DateTime.MinValue;
                _gitVersionAt = DateTime.MinValue;
                _uvCache = null;
                _gitCache = null;
                _pyCache = null;
                _pyCacheAt = DateTime.MinValue;
            }
        }

        public string ResolveUv()
        {
            lock (_cacheLock)
            {
                if (DateTime.Now - _uvCacheAt < TimeSpan.FromSeconds(20) && !string.IsNullOrEmpty(_uvCache))
                    return File.Exists(_uvCache) ? _uvCache : null;
                _uvCacheAt = DateTime.Now;
                _uvCache = null;
                if (File.Exists(UvLocal)) _uvCache = UvLocal;
                else _uvCache = ResolveFromPath("uv.exe");
                return _uvCache;
            }
        }

        public string ResolveGit()
        {
            lock (_cacheLock)
            {
                if (DateTime.Now - _gitCacheAt < TimeSpan.FromSeconds(20) && !string.IsNullOrEmpty(_gitCache))
                    return File.Exists(_gitCache) ? _gitCache : null;
                _gitCacheAt = DateTime.Now;
                _gitCache = null;
                if (File.Exists(GitLocal)) _gitCache = GitLocal;
                else _gitCache = ResolveFromPath("git.exe");
                return _gitCache;
            }
        }

        private static string ResolveFromPath(string name)
        {
            try
            {
                string path = Environment.GetEnvironmentVariable("PATH") ?? "";
                foreach (string part in path.Split(new char[] { ';' }, StringSplitOptions.RemoveEmptyEntries))
                {
                    try
                    {
                        string candidate = Path.Combine(part.Trim('"'), name);
                        if (File.Exists(candidate)) return candidate;
                    }
                    catch { }
                }
            }
            catch { }
            return null;
        }

        public string UvVersion()
        {
            lock (_cacheLock)
            {
                if (DateTime.Now - _uvVersionAt < TimeSpan.FromSeconds(60)) return _uvVersion;
            }
            string uv = ResolveUv();
            string version = "";
            if (uv != null)
            {
                ProcResult r = RunAsync(uv, new string[] { "--version" }, _paths.Runtime, CancellationToken.None, null, 10000).GetAwaiter().GetResult();
                if (r.ExitCode == 0) version = r.Output.FirstOrDefault() ?? "";
            }
            lock (_cacheLock)
            {
                _uvVersion = version.Trim();
                _uvVersionAt = DateTime.Now;
            }
            return _uvVersion;
        }

        public string GitVersion()
        {
            lock (_cacheLock)
            {
                if (DateTime.Now - _gitVersionAt < TimeSpan.FromSeconds(60)) return _gitVersion;
            }
            string git = ResolveGit();
            string version = "";
            if (git != null)
            {
                ProcResult r = RunAsync(git, new string[] { "--version" }, _paths.Runtime, CancellationToken.None, null, 10000).GetAwaiter().GetResult();
                if (r.ExitCode == 0) version = r.Output.FirstOrDefault() ?? "";
            }
            lock (_cacheLock)
            {
                _gitVersion = version.Trim();
                _gitVersionAt = DateTime.Now;
            }
            return _gitVersion;
        }

        public string FindPython(string version)
        {
            return FindPython(version, false);
        }

        public string FindPython(string version, bool force)
        {
            lock (_cacheLock)
            {
                if (!force && DateTime.Now - _pyCacheAt < TimeSpan.FromSeconds(30) &&
                    string.Equals(_pyCacheVersion, version, StringComparison.OrdinalIgnoreCase))
                    return _pyCache;
            }
            string uv = ResolveUv();
            if (uv == null) return "";
            ProcResult r = RunAsync(uv, new string[] { "python", "find", version, "--managed-python" }, _paths.Runtime, CancellationToken.None, null, 20000).GetAwaiter().GetResult();
            if (r.ExitCode != 0) return "";
            for (int i = r.Output.Count - 1; i >= 0; i--)
            {
                string candidate = (r.Output[i] ?? "").Trim();
                if (candidate.Length > 0 && File.Exists(candidate))
                {
                    lock (_cacheLock)
                    {
                        _pyCache = candidate;
                        _pyCacheVersion = version;
                        _pyCacheAt = DateTime.Now;
                    }
                    return candidate;
                }
            }
            lock (_cacheLock)
            {
                _pyCache = "";
                _pyCacheVersion = version;
                _pyCacheAt = DateTime.Now;
            }
            return "";
        }

        public async Task<ProcResult> InstallPython(string version, string pythonMirror, bool useMirror, CancellationToken ct)
        {
            string uv = ResolveUv();
            if (uv == null) throw new InvalidOperationException("未找到 uv");
            List<string> args = new List<string>();
            args.Add("python");
            args.Add("install");
            args.Add(version);
            args.Add("--no-bin");
            args.Add("--no-registry");
            if (useMirror && !string.IsNullOrEmpty(pythonMirror))
            {
                args.Add("--mirror");
                args.Add(pythonMirror);
            }
            return await RunAsync(uv, args, _paths.Runtime, ct, null, 0);
        }

        public async Task<ProcResult> CreateVenv(string baseDir, string pythonPath, CancellationToken ct)
        {
            string uv = ResolveUv();
            if (uv == null) throw new InvalidOperationException("未找到 uv");
            string venv = Path.Combine(baseDir, ".venv");
            List<string> args = new List<string>();
            args.Add("venv");
            args.Add(venv);
            args.Add("--python");
            args.Add(pythonPath);
            return await RunAsync(uv, args, baseDir, ct, null, 0);
        }

        public async Task<ProcResult> SyncDeps(string baseDir, string pythonPath, ProfileInfo profile, string pypi, bool mirrorCn, CancellationToken ct)
        {
            string uv = ResolveUv();
            if (uv == null) throw new InvalidOperationException("未找到 uv");
            List<string> baseArgs = new List<string>();
            baseArgs.Add("sync");
            baseArgs.Add("--project");
            baseArgs.Add(baseDir);
            baseArgs.Add("--python");
            baseArgs.Add(pythonPath);
            baseArgs.Add("--no-dev");
            if (!profile.IncludeAddons)
            {
                baseArgs.Add("--no-install-package");
                baseArgs.Add("pyside6-addons");
            }
            ProcResult result;
            if (mirrorCn)
            {
                List<string> args = new List<string>(baseArgs);
                args.Add("--locked");
                result = await RunAsync(uv, args, baseDir, ct, null, 0);
                if (result.ExitCode != 0 && !result.Cancelled)
                {
                    _log.Warn("锁定同步失败，回退到重新解析（新环境内，不影响其他版本）");
                    args = new List<string>(baseArgs);
                    args.Add("--default-index");
                    args.Add(pypi);
                    result = await RunAsync(uv, args, baseDir, ct, null, 0);
                }
                if (result.ExitCode != 0 && !result.Cancelled)
                {
                    _log.Warn("国内 PyPI 同步失败，回退官方源");
                    List<string> officialArgs = new List<string>(baseArgs);
                    officialArgs.Add("--default-index");
                    officialArgs.Add("https://pypi.org/simple");
                    result = await RunAsync(uv, officialArgs, baseDir, ct, null, 0);
                }
            }
            else
            {
                List<string> args = new List<string>(baseArgs);
                args.Add("--default-index");
                args.Add(pypi);
                result = await RunAsync(uv, args, baseDir, ct, null, 0);
            }
            return result;
        }

        public async Task<Dictionary<string, string>> GitLsRemote(string repo, bool github, CancellationToken ct)
        {
            Dictionary<string, string> map = new Dictionary<string, string>(StringComparer.Ordinal);
            string git = ResolveGit();
            if (git == null) return map;
            List<string> args = new List<string>();
            if (!github)
            {
                args.Add("-c");
                args.Add("http.lowSpeedLimit=1000");
                args.Add("-c");
                args.Add("http.lowSpeedTime=15");
            }
            args.Add("ls-remote");
            args.Add("--tags");
            args.Add("--heads");
            args.Add(repo);
            ProcResult r = await RunAsync(git, args, _paths.Runtime, ct, null, 90000);
            if (r.ExitCode != 0) throw new InvalidOperationException("无法读取远端版本：" + r.Tail(3));
            foreach (string line in r.Output)
            {
                if (line == null) continue;
                string[] parts = line.Split(new char[] { '\t', ' ' }, StringSplitOptions.RemoveEmptyEntries);
                if (parts.Length != 2) continue;
                map[parts[1].Trim()] = parts[0].Trim();
            }
            return map;
        }

        public async Task<ProcResult> GitClone(string repo, string refName, string dest, bool github, CancellationToken ct)
        {
            string git = ResolveGit();
            if (git == null) throw new InvalidOperationException("未找到 Git");
            List<string> args = new List<string>();
            if (!github)
            {
                args.Add("-c");
                args.Add("http.lowSpeedLimit=1000");
                args.Add("-c");
                args.Add("http.lowSpeedTime=15");
            }
            args.Add("clone");
            args.Add("--depth");
            args.Add("1");
            if (!string.IsNullOrEmpty(refName))
            {
                args.Add("--branch");
                args.Add(refName);
            }
            args.Add(repo);
            args.Add(dest);
            return await RunAsync(git, args, _paths.Runtime, ct, null, 0);
        }

        public string GitHead(string baseDir)
        {
            string git = ResolveGit();
            if (git == null || !Directory.Exists(baseDir)) return "";
            ProcResult r = RunAsync(git, new string[] { "-C", baseDir, "rev-parse", "HEAD" }, _paths.Runtime, CancellationToken.None, null, 15000).GetAwaiter().GetResult();
            if (r.ExitCode != 0) return "";
            return (r.Output.FirstOrDefault() ?? "").Trim();
        }

        public string GitStatus(string baseDir)
        {
            string git = ResolveGit();
            if (git == null || !Directory.Exists(baseDir)) return "";
            ProcResult r = RunAsync(git, new string[] { "-C", baseDir, "status", "--porcelain", "--untracked-files=normal" }, _paths.Runtime, CancellationToken.None, null, 20000).GetAwaiter().GetResult();
            if (r.ExitCode != 0) return "";
            return string.Join("\n", r.Output.ToArray());
        }

        public ProcResult CheckPySide6(string baseDir, string venvPath)
        {
            string python = Path.Combine(venvPath, "Scripts", "python.exe");
            if (!File.Exists(python)) return new ProcResult { ExitCode = -1 };
            return RunAsync(python, new string[] { "-c", "import PySide6; print(PySide6.__version__)" }, baseDir, CancellationToken.None, null, 30000).GetAwaiter().GetResult();
        }

        public Task<ProcResult> RunAsync(string exe, IEnumerable<string> args, string cwd, CancellationToken ct, Action<string> onLine, int timeoutMs)
        {
            ProcResult result = new ProcResult();
            if (string.IsNullOrEmpty(exe) || !File.Exists(exe))
            {
                result.Output.Add("找不到可执行文件：" + (exe ?? "(null)"));
                return Task.FromResult(result);
            }
            ProcessStartInfo psi = new ProcessStartInfo();
            psi.FileName = exe;
            psi.Arguments = Util.JoinArgs(args ?? new string[0]);
            psi.WorkingDirectory = string.IsNullOrEmpty(cwd) ? _paths.Runtime : cwd;
            psi.UseShellExecute = false;
            psi.CreateNoWindow = true;
            psi.WindowStyle = ProcessWindowStyle.Hidden;
            psi.RedirectStandardOutput = true;
            psi.RedirectStandardError = true;
            psi.StandardOutputEncoding = Encoding.UTF8;
            psi.StandardErrorEncoding = Encoding.UTF8;
            psi.EnvironmentVariables["GIT_TERMINAL_PROMPT"] = "0";
            psi.EnvironmentVariables["UV_NO_PROGRESS"] = "1";
            psi.EnvironmentVariables["UV_NO_MODIFY_PATH"] = "1";
            psi.EnvironmentVariables["UV_CACHE_DIR"] = _paths.UvCache;
            psi.EnvironmentVariables["UV_PYTHON_INSTALL_DIR"] = _paths.PythonDir;
            psi.EnvironmentVariables["PYTHONUTF8"] = "1";
            psi.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
            _log.Cmd(Path.GetFileName(exe) + " " + psi.Arguments);

            object gate = new object();
            Process p = new Process();
            p.StartInfo = psi;
            p.OutputDataReceived += delegate(object sender, DataReceivedEventArgs e)
            {
                if (e.Data == null) return;
                string line = e.Data.TrimEnd();
                if (line.Length == 0) return;
                lock (gate) result.Output.Add(line);
                _log.Out(line);
                if (onLine != null) { try { onLine(line); } catch { } }
            };
            p.ErrorDataReceived += delegate(object sender, DataReceivedEventArgs e)
            {
                if (e.Data == null) return;
                string line = e.Data.TrimEnd();
                if (line.Length == 0) return;
                lock (gate) result.Output.Add(line);
                _log.Out(line);
                if (onLine != null) { try { onLine(line); } catch { } }
            };
            try
            {
                p.Start();
                p.BeginOutputReadLine();
                p.BeginErrorReadLine();
                DateTime started = DateTime.Now;
                while (!p.WaitForExit(200))
                {
                    if (ct.IsCancellationRequested)
                    {
                        result.Cancelled = true;
                        Util.KillTree(p.Id);
                        break;
                    }
                    if (timeoutMs > 0 && (DateTime.Now - started).TotalMilliseconds > timeoutMs)
                    {
                        result.TimedOut = true;
                        Util.KillTree(p.Id);
                        break;
                    }
                }
                if (!p.HasExited)
                {
                    try { p.WaitForExit(5000); } catch { }
                }
                try { p.WaitForExit(); } catch { }
                result.ExitCode = p.HasExited ? p.ExitCode : -1;
            }
            catch (Exception ex)
            {
                result.Output.Add(ex.Message);
                _log.Err(ex.Message);
            }
            finally
            {
                try { p.Dispose(); } catch { }
            }
            return Task.FromResult(result);
        }
    }
}
