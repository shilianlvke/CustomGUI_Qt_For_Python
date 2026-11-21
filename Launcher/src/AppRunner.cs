using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading;

namespace SllkGui.Launcher
{
    internal sealed class AppRunner
    {
        private readonly LauncherPaths _paths;
        private readonly Config _config;
        private readonly EnvManager _env;
        private readonly Toolchain _tools;
        private readonly LogBuffer _log;
        private readonly object _lock = new object();
        private readonly List<string> _tail = new List<string>();
        private Process _process;
        private DateTime _lastCheck = DateTime.MinValue;
        private bool _lastRunning;

        public AppRunner(LauncherPaths paths, Config config, EnvManager env, Toolchain tools, LogBuffer log)
        {
            _paths = paths;
            _config = config;
            _env = env;
            _tools = tools;
            _log = log;
        }

        public int Pid { get; private set; }

        public bool IsRunning()
        {
            lock (_lock)
            {
                if (DateTime.Now - _lastCheck < TimeSpan.FromSeconds(2)) return _lastRunning;
                _lastCheck = DateTime.Now;
                _lastRunning = false;
                Pid = 0;

                int pid;
                DateTime started;
                if (ReadAppState(out pid, out started) && Util.IsProcessAlive(pid, started))
                {
                    _lastRunning = true;
                    Pid = pid;
                    return true;
                }

                foreach (string name in new string[] { "python", "pythonw", "sllkgui" })
                {
                    try
                    {
                        Process[] all = Process.GetProcessesByName(name);
                        foreach (Process p in all)
                        {
                            try
                            {
                                string title = p.MainWindowTitle;
                                if (!string.IsNullOrEmpty(title) && title.IndexOf("SllkGui", StringComparison.OrdinalIgnoreCase) >= 0)
                                {
                                    _lastRunning = true;
                                    Pid = p.Id;
                                    return true;
                                }
                            }
                            catch { }
                            finally { try { p.Dispose(); } catch { } }
                        }
                    }
                    catch { }
                }
                return false;
            }
        }

        private bool ReadAppState(out int pid, out DateTime started)
        {
            pid = 0;
            started = DateTime.MinValue;
            try
            {
                if (!File.Exists(_paths.AppJsonPath)) return false;
                Dictionary<string, object> d = Json.ParseObject(File.ReadAllText(_paths.AppJsonPath));
                pid = Json.Int(d, "pid", 0);
                string text = Json.Str(d, "startedAt", "");
                DateTime.TryParse(text, null, System.Globalization.DateTimeStyles.RoundtripKind, out started);
                return pid > 0 && started != DateTime.MinValue;
            }
            catch { return false; }
        }

        public Dictionary<string, object> Launch()
        {
            Dictionary<string, object> result = new Dictionary<string, object>();
            if (IsRunning())
            {
                result["ok"] = true;
                result["already"] = true;
                result["pid"] = Pid;
                return result;
            }
            EnvRecord env = _env.Current;
            if (env == null || !_env.IsValid(env))
            {
                result["ok"] = false;
                result["error"] = "环境尚未就绪，请先初始化";
                return result;
            }
            string uv = _tools.ResolveUv();
            if (uv == null)
            {
                result["ok"] = false;
                result["error"] = "未找到 uv，请重新初始化";
                return result;
            }
            string baseDir = env.ResolveBase(_paths);
            string dataDir = _paths.DataDir;
            Directory.CreateDirectory(dataDir);
            string pypi = _managerPypi();

            List<string> args = new List<string>();
            args.Add("run");
            args.Add("--project");
            args.Add(baseDir);
            args.Add("--no-sync");
            args.Add("sllkgui");
            args.Add(_config.Mode == "gallery" ? "gallery" : "run");
            args.Add("--data-dir");
            args.Add(dataDir);
            if (!string.IsNullOrEmpty(pypi))
            {
                args.Add("--index-url");
                args.Add(pypi);
            }
            if (_config.SafeMode) args.Add("--safe-mode");
            if (_config.NoPluginDeps) args.Add("--no-install-deps");

            string outPath = Path.Combine(_paths.Logs, "app.out.log");
            string errPath = Path.Combine(_paths.Logs, "app.err.log");
            ProcessStartInfo psi = new ProcessStartInfo();
            psi.FileName = uv;
            psi.Arguments = Util.JoinArgs(args);
            psi.WorkingDirectory = baseDir;
            psi.UseShellExecute = false;
            psi.CreateNoWindow = true;
            psi.WindowStyle = ProcessWindowStyle.Hidden;
            psi.RedirectStandardOutput = true;
            psi.RedirectStandardError = true;
            psi.StandardOutputEncoding = Encoding.UTF8;
            psi.StandardErrorEncoding = Encoding.UTF8;
            psi.EnvironmentVariables["UV_NO_PROGRESS"] = "1";
            psi.EnvironmentVariables["UV_CACHE_DIR"] = _paths.UvCache;
            psi.EnvironmentVariables["UV_PYTHON_INSTALL_DIR"] = _paths.PythonDir;
            psi.EnvironmentVariables["PYTHONUTF8"] = "1";
            psi.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";

            _log.Cmd("uv " + psi.Arguments);
            Process p = new Process();
            p.StartInfo = psi;
            p.OutputDataReceived += delegate(object s, DataReceivedEventArgs e) { Append(outPath, "out", e.Data); };
            p.ErrorDataReceived += delegate(object s, DataReceivedEventArgs e) { Append(errPath, "err", e.Data); };
            try
            {
                p.Start();
                p.BeginOutputReadLine();
                p.BeginErrorReadLine();
                _process = p;
                DateTime started = p.StartTime.ToUniversalTime();
                Dictionary<string, object> state = new Dictionary<string, object>();
                state["pid"] = p.Id;
                state["startedAt"] = started.ToString("o");
                state["basePath"] = env.BasePath;
                state["ref"] = env.Ref;
                state["sha"] = env.Sha;
                state["mode"] = _config.Mode;
                Util.AtomicWriteAllText(_paths.AppJsonPath, Json.Stringify(state));
                _log.Ok("基座已启动 · PID " + p.Id);

                DateTime begin = DateTime.Now;
                while ((DateTime.Now - begin).TotalSeconds < 6)
                {
                    if (p.HasExited) break;
                    Thread.Sleep(200);
                }
                if (p.HasExited)
                {
                    int code = -1;
                    try { code = p.ExitCode; } catch { }
                    Util.TryDeleteFile(_paths.AppJsonPath);
                    string tail = TailAppLog(12);
                    _log.Err("基座启动失败，退出码 " + code);
                    result["ok"] = false;
                    result["error"] = "基座启动失败（退出码 " + code + "）" + (tail.Length > 0 ? "：" + tail : "");
                    return result;
                }
                Pid = p.Id;
                _lastCheck = DateTime.Now;
                _lastRunning = true;
                result["ok"] = true;
                result["pid"] = p.Id;
                return result;
            }
            catch (Exception ex)
            {
                Util.TryDeleteFile(_paths.AppJsonPath);
                _log.Err("启动基座失败：" + ex.Message);
                result["ok"] = false;
                result["error"] = ex.Message;
                return result;
            }
        }

        private string _managerPypi()
        {
            try
            {
                Manifest manifest = Manifest.Load();
                return manifest.Mirror(_config.Mirror).Pypi;
            }
            catch { return ""; }
        }

        private void Append(string path, string level, string text)
        {
            if (text == null) return;
            string clean = Util.StripAnsi(text);
            lock (_lock)
            {
                _tail.Add(clean);
                if (_tail.Count > 300) _tail.RemoveRange(0, _tail.Count - 300);
            }
            try
            {
                string dir = Path.GetDirectoryName(path);
                if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);
                FileInfo fi = new FileInfo(path);
                if (fi.Exists && fi.Length > 5 * 1024 * 1024)
                {
                    string old = path + ".1";
                    try { if (File.Exists(old)) File.Delete(old); File.Move(path, old); } catch { }
                }
                File.AppendAllText(path, clean + Environment.NewLine, new UTF8Encoding(false));
            }
            catch { }
        }

        public Dictionary<string, object> Stop()
        {
            Dictionary<string, object> result = new Dictionary<string, object>();
            int pid = 0;
            DateTime started;
            if (ReadAppState(out pid, out started) && Util.IsProcessAlive(pid, started))
            {
                Util.KillTree(pid);
                _log.Warn("已请求关闭基座 · PID " + pid);
                result["ok"] = true;
                result["pid"] = pid;
            }
            else
            {
                result["ok"] = false;
                result["error"] = "基座未在运行";
            }
            Util.TryDeleteFile(_paths.AppJsonPath);
            lock (_lock)
            {
                _lastCheck = DateTime.MinValue;
                _lastRunning = false;
                Pid = 0;
                try { if (_process != null && !_process.HasExited) Util.KillTree(_process.Id); } catch { }
            }
            return result;
        }

        public string TailAppLog(int max)
        {
            string latest = LatestAppLog();
            if (string.IsNullOrEmpty(latest))
            {
                string err = Path.Combine(_paths.Logs, "app.err.log");
                if (File.Exists(err) && new FileInfo(err).Length > 0) latest = err;
                else
                {
                    string outp = Path.Combine(_paths.Logs, "app.out.log");
                    if (File.Exists(outp) && new FileInfo(outp).Length > 0) latest = outp;
                }
            }
            if (string.IsNullOrEmpty(latest))
            {
                lock (_lock)
                {
                    int start = Math.Max(0, _tail.Count - max);
                    return string.Join(Environment.NewLine, _tail.Skip(start).ToArray());
                }
            }
            string[] lines = Util.ReadTail(latest, max);
            for (int i = 0; i < lines.Length; i++) lines[i] = Util.StripAnsi(lines[i]);
            return string.Join(Environment.NewLine, lines);
        }

        public string LatestAppLog()
        {
            try
            {
                string dir = Path.Combine(_paths.DataDir, "logs");
                if (Directory.Exists(dir))
                {
                    FileInfo latest = null;
                    foreach (string file in Directory.GetFiles(dir, "*.log"))
                    {
                        FileInfo fi = new FileInfo(file);
                        if (latest == null || fi.LastWriteTime > latest.LastWriteTime) latest = fi;
                    }
                    if (latest != null) return latest.FullName;
                }
            }
            catch { }
            return "";
        }

        public List<string> AppLogLines(int max)
        {
            string path = LatestAppLog();
            if (string.IsNullOrEmpty(path)) return new List<string>();
            string[] lines = Util.ReadTail(path, max);
            for (int i = 0; i < lines.Length; i++) lines[i] = Util.StripAnsi(lines[i]);
            return lines.ToList();
        }
    }
}
