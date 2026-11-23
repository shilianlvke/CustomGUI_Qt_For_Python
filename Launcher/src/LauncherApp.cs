using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography.X509Certificates;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace SllkGui.Launcher
{
    internal sealed class LauncherApp
    {
        private readonly LauncherPaths _paths;
        private readonly Manifest _manifest;
        private readonly Config _config;
        private readonly LogBuffer _log;
        private readonly LauncherState _state;
        private readonly Toolchain _tools;
        private readonly EnvManager _env;
        private readonly AppRunner _app;
        private readonly Bootstrap _bootstrap;
        private readonly HttpServer _http;
        private readonly string _token;
        private readonly string _nonce;
        private readonly DateTime _startedAt = DateTime.Now;
        private readonly Dictionary<string, DateTime> _clients = new Dictionary<string, DateTime>(StringComparer.Ordinal);
        private DateTime _lastRequest = DateTime.Now;
        private DateTime? _byeAt;
        private volatile bool _shutdown;
        private System.Threading.Timer _timer;
        private Dictionary<string, object> _versionsCache;
        private DateTime _versionsAt = DateTime.MinValue;
        private string _dirtyCache = "";
        private DateTime _dirtyAt = DateTime.MinValue;
        private long _diskCache;
        private string _diskEnvId = "";
        private DateTime _diskAt = DateTime.MinValue;
        private bool? _signed;

        public int Port { get; private set; }
        public string Token { get { return _token; } }
        public bool ShutdownRequested { get { return _shutdown; } }

        public LauncherApp(LauncherPaths paths, Manifest manifest, Config config, LogBuffer log)
        {
            _paths = paths;
            _manifest = manifest;
            _config = config;
            _log = log;
            _state = new LauncherState();
            _tools = new Toolchain(paths, manifest, log);
            _env = new EnvManager(paths, manifest, log);
            _env.Load();
            _app = new AppRunner(paths, config, _env, _tools, log);
            _bootstrap = new Bootstrap(paths, config, manifest, _env, _tools, log, _state);
            _http = new HttpServer(Handle, log);
            _token = Util.RandomHex(16);
            _nonce = Util.RandomHex(12);
            lock (_state.Lock)
            {
                _state.Phase = _env.Current != null && _env.IsValid(_env.Current) ? "done" : "idle";
            }
        }

        public void Start(bool noBrowser, int preferredPort)
        {
            _paths.Ensure();
            _http.Start(preferredPort);
            Port = _http.Port;
            WritePortFiles();
            _timer = new System.Threading.Timer(Tick, null, 1000, 1000);
            _log.Sys("SllkGui Launcher " + _manifest.LauncherVersion + " · 运行时 " + _paths.Runtime);
            if (_env.Current != null)
                _log.Ok("当前环境 · " + _env.Current.Ref + " · " + ShortSha(_env.Current.Sha) + " · " + _env.Current.Profile);
            else
                _log.Sys("尚未初始化环境");
            if (!noBrowser)
            {
                string url = Url();
                try { Util.OpenUrl(url); }
                catch (Exception ex)
                {
                    _log.Warn("无法打开系统浏览器：" + ex.Message);
                    try { MessageBox.Show("无法调用系统浏览器，请手动打开：\r\n" + url, "SllkGui 启动器", MessageBoxButtons.OK, MessageBoxIcon.Warning); } catch { }
                }
            }
            if (_config.AutoLaunch && _env.Current != null && _env.IsValid(_env.Current) && !_app.IsRunning())
            {
                Task.Run(delegate
                {
                    Thread.Sleep(1200);
                    if (!_shutdown) _app.Launch();
                });
            }
        }

        public void Stop()
        {
            if (_shutdown && _timer == null) return;
            _shutdown = true;
            try { _app.Dispose(); } catch { }
            try { _bootstrap.Cancel(); } catch { }
            try { _http.Stop(); } catch { }
            try { if (_timer != null) _timer.Dispose(); } catch { }
            _timer = null;
            try { Util.TryDeleteFile(_paths.PortJsonPath); } catch { }
            try { File.AppendAllText(Path.Combine(_paths.Logs, "launcher.log"), DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + " launcher exit\r\n"); } catch { }
        }

        public string Url()
        {
            return "http://127.0.0.1:" + Port + "/";
        }

        public Dictionary<string, object> LaunchOnly()
        {
            return _app.Launch();
        }

        private void WritePortFiles()
        {
            Dictionary<string, object> d = new Dictionary<string, object>();
            d["port"] = Port;
            d["pid"] = System.Diagnostics.Process.GetCurrentProcess().Id;
            d["startedAt"] = _startedAt.ToUniversalTime().ToString("o");
            d["url"] = Url();
            try { Util.AtomicWriteAllText(_paths.PortJsonPath, Json.Stringify(d)); } catch { }
        }

        private void Tick(object ignored)
        {
            try
            {
                if (_shutdown)
                {
                    Stop();
                    return;
                }
                bool busy = _bootstrap.Busy;
                if (_byeAt.HasValue && _config.CloseWithPage && !busy &&
                    (DateTime.Now - _byeAt.Value).TotalSeconds > 5)
                {
                    _log.Sys("页面已关闭，启动器退出");
                    _shutdown = true;
                    Stop();
                    return;
                }
                if (!busy && (DateTime.Now - _lastRequest).TotalSeconds > 600)
                {
                    _log.Sys("长时间无请求，启动器退出");
                    _shutdown = true;
                    Stop();
                }
            }
            catch { }
        }

        private HttpResponse Handle(HttpRequest request)
        {
            _lastRequest = DateTime.Now;
            string path = request.Path ?? "/";
            if (request.Method == "OPTIONS")
            {
                HttpResponse opt = HttpResponse.Empty(204);
                opt.Headers["Allow"] = "GET, POST, HEAD, OPTIONS";
                return opt;
            }
            if (path == "/" || path == "/index.html")
            {
                _byeAt = null;
                string html = Resources.UiHtml().Replace("__TOKEN__", _token).Replace("__NONCE__", _nonce);
                HttpResponse r = HttpResponse.Html(html);
                r.Headers["Content-Security-Policy"] =
                    "default-src 'none'; script-src 'nonce-" + _nonce + "'; style-src 'self' 'unsafe-inline'; " +
                    "img-src 'self' data:; connect-src 'self'; font-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'";
                return r;
            }
            if (path == "/favicon.ico")
            {
                return HttpResponse.Bytes(Resources.Icon(), "image/x-icon");
            }
            if (path == "/mihoutao.svg")
            {
                return HttpResponse.Bytes(Encoding.UTF8.GetBytes(Resources.MihoutaoSvg()), "image/svg+xml; charset=utf-8");
            }
            if (path.StartsWith("/api/", StringComparison.OrdinalIgnoreCase))
            {
                if (!Util.FixedTimeEquals(request.Header("x-token"), _token))
                    return Forbidden();
                string sid = QueryValue(request.Query, "sid");
                if (!string.IsNullOrEmpty(sid) && path != "/api/bye")
                {
                    _clients[sid] = DateTime.Now;
                    if (_clients.Count > 24)
                    {
                        DateTime cut = DateTime.Now.AddMinutes(-5);
                        List<string> stale = _clients.Where(delegate(KeyValuePair<string, DateTime> kv) { return kv.Value < cut; })
                            .Select(delegate(KeyValuePair<string, DateTime> kv) { return kv.Key; }).ToList();
                        foreach (string key in stale) _clients.Remove(key);
                    }
                }
                try
                {
                    return Route(request, path);
                }
                catch (Exception ex)
                {
                    _log.Err("接口异常 " + path + "：" + ex.Message);
                    return Error(ex.Message);
                }
            }
            return HttpResponse.Text("not found", 404);
        }

        private HttpResponse Route(HttpRequest request, string path)
        {
            switch (path)
            {
                case "/api/state":
                    return HttpResponse.Json(BuildState(false));
                case "/api/log":
                    return HttpResponse.Json(_log.Snapshot(QueryInt(request.Query, "cursor", 0)));
                case "/api/versions":
                    return HttpResponse.Json(BuildVersion(_env.Current, QueryBool(request.Query, "refresh")));
                case "/api/config":
                    return HandleConfig(request);
                case "/api/mode":
                    return HandleMode(request);
                case "/api/setup":
                    return HandleSetup(request);
                case "/api/setup/stop":
                    _bootstrap.Cancel();
                    return Ok();
                case "/api/update":
                    return HandleUpdate(request);
                case "/api/update/stop":
                    _bootstrap.Cancel();
                    return Ok();
                case "/api/sync":
                    return HandleSync(request);
                case "/api/launch":
                    return HttpResponse.Json(_app.Launch());
                case "/api/stop":
                    return HttpResponse.Json(_app.Stop());
                case "/api/repair":
                    return HandleRepair();
                case "/api/rollback":
                    return HandleRollback();
                case "/api/cleanup":
                    return HandleCleanup();
                case "/api/dirty":
                    return HttpResponse.Json(Dirty(true));
                case "/api/health":
                    return HttpResponse.Json(BuildHealth(_env.Current, _app.IsRunning()));
                case "/api/diagnostics":
                    return HttpResponse.Json(Diagnostics());
                case "/api/applog":
                    return HttpResponse.Json(AppLog());
                case "/api/open":
                    try { Util.OpenFolder(_paths.Logs); } catch { }
                    return Ok();
                case "/api/exit":
                    if (_bootstrap.Busy) return Error("初始化或更新进行中，请先停止后再退出");
                    _shutdown = true;
                    return Ok();
                case "/api/bye":
                    HandleBye(request.Query);
                    return Ok();
                default:
                    HttpResponse missing = HttpResponse.Json(new Dictionary<string, object> { { "ok", false }, { "error", "not found" } });
                    missing.Status = 404;
                    return missing;
            }
        }

        private HttpResponse HandleConfig(HttpRequest request)
        {
            if (request.Method == "GET")
                return HttpResponse.Json(_config.ToDto(_manifest, _paths.Runtime, _manifest.LauncherVersion));
            Dictionary<string, object> body = ParseBody(request);
            if (_app.IsRunning() && body.ContainsKey("mode")) return Error("基座运行中，不能切换模式");
            string error;
            lock (_config)
            {
                error = _config.ApplyDto(body, _manifest);
                if (string.IsNullOrEmpty(error)) _config.Save(_paths.ConfigPath);
            }
            if (!string.IsNullOrEmpty(error)) return Error(error);
            Dictionary<string, object> state = BuildState(false);
            state["saved"] = true;
            return HttpResponse.Json(state);
        }

        private HttpResponse HandleMode(HttpRequest request)
        {
            Dictionary<string, object> body = ParseBody(request);
            string mode = Json.Str(body, "mode", "");
            if (mode != "run" && mode != "gallery") return Error("模式参数不合法");
            if (_app.IsRunning()) return Error("基座正在运行，不能切换模式");
            lock (_config)
            {
                _config.Mode = mode;
                _config.Save(_paths.ConfigPath);
            }
            return HttpResponse.Json(new Dictionary<string, object> { { "ok", true }, { "mode", mode } });
        }

        private HttpResponse HandleSetup(HttpRequest request)
        {
            if (_app.IsRunning()) return Error("基座正在运行，请先关闭基座再初始化");
            if (_bootstrap.Busy) return Error("busy");
            Dictionary<string, object> body = ParseBody(request);
            string profile = Json.Str(body, "profile", _config.Profile);
            string mirror = Json.Str(body, "mirror", _config.Mirror);
            if (!Config.IsKnownProfile(profile, _manifest)) return Error("安装配置不合法");
            try
            {
                _bootstrap.StartSetup(profile, mirror);
                return Ok();
            }
            catch (Exception ex)
            {
                return Error(ex.Message);
            }
        }

        private HttpResponse HandleUpdate(HttpRequest request)
        {
            Dictionary<string, object> body = ParseBody(request);
            string refName = Json.Str(body, "ref", "");
            if (!Config.IsValidBranch(refName)) return Error("版本号不合法");
            if (_app.IsRunning()) return Error("基座正在运行，请先关闭基座再更新");
            if (_bootstrap.Busy) return Error("busy");
            EnvRecord current = _env.Current;
            if (current == null || !string.Equals(current.SourceKind, "git", StringComparison.OrdinalIgnoreCase) || _tools.ResolveGit() == null)
                return Error("当前为轻量安装，不支持版本切换；请重新初始化并选择标准或完整配置");
            try
            {
                _bootstrap.StartUpdate(refName, false);
                return Ok();
            }
            catch (Exception ex)
            {
                return Error(ex.Message);
            }
        }

        private HttpResponse HandleSync(HttpRequest request)
        {
            Dictionary<string, object> body = ParseBody(request);
            string refName = Json.Str(body, "ref", "main");
            if (refName != "main") return Error("当前仅支持同步到 main；请使用版本选择更新到指定 tag");
            if (_app.IsRunning()) return Error("基座正在运行，请先关闭基座再更新");
            if (_bootstrap.Busy) return Error("busy");
            EnvRecord current = _env.Current;
            if (current == null || !string.Equals(current.SourceKind, "git", StringComparison.OrdinalIgnoreCase) || _tools.ResolveGit() == null)
                return Error("当前为轻量安装，不支持同步；请重新初始化并选择标准或完整配置");
            try
            {
                _bootstrap.StartUpdate("main", false);
                Dictionary<string, object> d = new Dictionary<string, object>();
                d["ok"] = true;
                d["note"] = "更新会构建独立的新环境，不会修改或丢弃当前环境的本地改动";
                return HttpResponse.Json(d);
            }
            catch (Exception ex)
            {
                return Error(ex.Message);
            }
        }

        private HttpResponse HandleRepair()
        {
            if (_app.IsRunning()) return Error("基座正在运行，请先关闭基座再修复");
            if (_bootstrap.Busy) return Error("busy");
            try { _bootstrap.StartRepair(); return Ok(); }
            catch (Exception ex) { return Error(ex.Message); }
        }

        private HttpResponse HandleRollback()
        {
            if (_app.IsRunning()) return Error("基座正在运行，请先关闭基座再回滚");
            if (_bootstrap.Busy) return Error("busy");
            if (!_env.Rollback()) return Error("没有可回滚的上一环境");
            lock (_state.Lock)
            {
                _state.Phase = "done";
                _state.Error = "";
            }
            _log.Ok("已回滚到上一环境 · " + _env.Current.Id);
            return HttpResponse.Json(BuildState(false));
        }

        private HttpResponse HandleCleanup()
        {
            if (_bootstrap.Busy) return Error("busy");
            _log.Sys("清理请求：开始");
            Dictionary<string, object> result = _env.Cleanup();
            _diskAt = DateTime.MinValue;
            _log.Ok("已清理旧环境与缓存 · 释放 " + Json.Str(result, "freedText", "0 B"));
            _log.Sys("清理请求：完成");
            return HttpResponse.Json(result);
        }

        private void HandleBye(string query)
        {
            string sid = QueryValue(query, "sid");
            if (!string.IsNullOrEmpty(sid)) _clients.Remove(sid);
            bool alive = false;
            DateTime now = DateTime.Now;
            foreach (KeyValuePair<string, DateTime> kv in _clients)
            {
                if ((now - kv.Value).TotalSeconds <= 5) { alive = true; break; }
            }
            if (!alive) _byeAt = now;
        }

        private Dictionary<string, object> BuildState(bool refreshVersions)
        {
            EnvRecord env = _env.Current;
            bool running = _app.IsRunning();
            bool busy = _bootstrap.Busy;
            string phase;
            string error = "";
            string currentStep = "";
            DateTime? started = null;
            DateTime? finished = null;
            Dictionary<string, object> summary = null;
            DownloadProgress download;
            lock (_state.Lock)
            {
                phase = _state.Phase;
                error = _state.Error;
                currentStep = _state.Current;
                started = _state.StartedAt;
                finished = _state.FinishedAt;
                summary = _state.SyncSummary;
                download = new DownloadProgress
                {
                    Active = _state.Download.Active,
                    Label = _state.Download.Label,
                    Received = _state.Download.Received,
                    Total = _state.Download.Total,
                    Percent = _state.Download.Percent,
                    Text = _state.Download.Text
                };
            }
            if (busy && (phase == "setup" || phase == "update")) { }
            else if (running) phase = "running";
            else if (phase == "error") { }
            else if (env != null && _env.IsValid(env)) phase = "done";
            else phase = "idle";

            bool ready = env != null && _env.IsValid(env) && _tools.ResolveUv() != null;
            List<object> steps = BuildSteps(env);
            int done = 0;
            foreach (object item in steps)
            {
                Dictionary<string, object> d = item as Dictionary<string, object>;
                if (d != null && Json.Str(d, "state", "") == "ok") done++;
            }
            int elapsed = 0;
            if (started.HasValue)
            {
                DateTime end = finished.HasValue ? finished.Value : DateTime.Now;
                elapsed = Math.Max(0, (int)(end - started.Value).TotalSeconds);
            }
            ProfileInfo profile = _manifest.Profile(_config.Profile);
            MirrorInfo mirror = _manifest.Mirror(_config.Mirror);
            Dictionary<string, object> state = new Dictionary<string, object>();
            state["phase"] = phase;
            state["ready"] = ready;
            state["mirror"] = _config.Mirror;
            state["mirrorLabel"] = mirror.Label;
            state["mode"] = _config.Mode;
            state["modeLabel"] = _config.Mode == "gallery" ? "预览模式" : "正式模式";
            state["profile"] = profile.Name;
            state["profileLabel"] = profile.Label;
            state["downloadMb"] = profile.DownloadMb;
            state["installedMb"] = profile.InstalledMb;
            state["progress"] = done;
            state["total"] = 7;
            state["current"] = currentStep;
            state["elapsed"] = elapsed;
            state["error"] = phase == "error" ? error : "";
            state["running"] = running;
            state["pid"] = running ? _app.Pid : 0;
            state["owned"] = running && _app.Pid > 0;
            state["appLogAvailable"] = _app.LogAvailable;
            state["appExitNotice"] = running ? "" : _app.AppExitNotice;
            state["steps"] = steps;
            state["paths"] = new Dictionary<string, object>
            {
                { "base", env == null ? "" : env.ResolveBase(_paths) },
                { "runtime", _paths.Runtime },
                { "logs", _paths.Logs },
                { "data", _paths.DataDir }
            };
            state["repo"] = _config.Repo;
            state["python"] = _config.Python;
            state["port"] = Port;
            state["version"] = BuildVersion(env, refreshVersions);
            state["update"] = new Dictionary<string, object>
            {
                { "active", busy && phase == "update" },
                { "ref", _bootstrap.Busy ? _state.UpdateRef : "" },
                { "summary", summary }
            };
            state["env"] = env == null ? null : EnvDto(env);
            state["health"] = BuildHealth(env, running);
            state["download"] = download.ToDto();
            state["config"] = _config.ToDto(_manifest, _paths.Runtime, _manifest.LauncherVersion);
            state["launcher"] = new Dictionary<string, object>
            {
                { "version", _manifest.LauncherVersion },
                { "signed", IsSigned() },
                { "runtime", _paths.Runtime },
                { "port", Port }
            };
            state["capabilities"] = new Dictionary<string, object>
            {
                { "updatable", Updatable(env) },
                { "canRepair", env != null && !busy && !running },
                { "canRollback", _env.Previous != null && _env.IsValid(_env.Previous) && !busy && !running },
                { "canStopApp", running },
                { "canCleanup", !busy }
            };
            state["source"] = "csharp";
            return state;
        }

        private Dictionary<string, object> EnvDto(EnvRecord env)
        {
            Dictionary<string, object> d = env.ToDto();
            d["profileLabel"] = _manifest.Profile(env.Profile).Label;
            d["entry"] = env.EntryPath(_paths);
            d["baseDir"] = env.ResolveBase(_paths);
            d["venvDir"] = env.ResolveVenv(_paths);
            d["diskBytes"] = DiskBytes(env);
            d["diskText"] = Util.FormatBytes(DiskBytes(env));
            d["valid"] = _env.IsValid(env);
            return d;
        }

        private long DiskBytes(EnvRecord env)
        {
            string id = env == null ? "" : env.Id;
            if (string.Equals(_diskEnvId, id, StringComparison.OrdinalIgnoreCase) &&
                (DateTime.Now - _diskAt).TotalSeconds < 30)
                return _diskCache;
            _diskCache = _env.DiskBytes(env);
            _diskEnvId = id;
            _diskAt = DateTime.Now;
            return _diskCache;
        }

        private List<object> BuildSteps(EnvRecord env)
        {
            List<object> list = new List<object>();
            list.Add(Step("uv", "uv 包管理器", "uv", "uv.exe", env));
            list.Add(Step("python", "CPython 解释器", "cpython", _config.Python, env));
            bool useGit = env != null
                ? string.Equals(env.SourceKind, "git", StringComparison.OrdinalIgnoreCase)
                : _manifest.Profile(_config.Profile).UseGit;
            list.Add(Step("git", "Git 客户端", "git", useGit ? "git" : "轻量配置跳过", env));
            list.Add(Step("source", "基座源码", "source", "git clone / archive", env));
            list.Add(Step("venv", "虚拟环境", "venv", "uv venv", env));
            list.Add(Step("deps", "依赖同步", "deps", "uv sync", env));
            list.Add(Step("verify", "启动校验", "verify", "PySide6", env));
            return list;
        }

        private Dictionary<string, object> Step(string id, string label, string shortName, string hint, EnvRecord env)
        {
            string state = "wait";
            string note = hint;
            bool busy = _bootstrap.Busy;
            lock (_state.Lock)
            {
                StepState s;
                if (_state.Steps.TryGetValue(id, out s))
                {
                    state = s.State;
                    note = s.Note;
                }
                else if (busy)
                {
                    // 管线运行中，尚未到达的步骤不做额外探测，避免每秒启动 uv/git 子进程
                }
                else
                {
                    if (id == "uv" && _tools.ResolveUv() != null) { state = "ok"; note = _tools.UvVersion(); }
                    if (id == "python" && !string.IsNullOrEmpty(_tools.FindPython(_config.Python))) { state = "ok"; note = _config.Python; }
                    if (id == "git")
                    {
                        bool useGit = env != null
                            ? string.Equals(env.SourceKind, "git", StringComparison.OrdinalIgnoreCase)
                            : _manifest.Profile(_config.Profile).UseGit;
                        if (!useGit) { state = "ok"; note = "轻量配置跳过"; }
                        else if (_tools.ResolveGit() != null) { state = "ok"; note = _tools.GitVersion(); }
                    }
                    if (id == "source" && env != null) { state = "ok"; note = env.Ref + " · " + ShortSha(env.Sha); }
                    if (id == "venv" && env != null && _env.IsValid(env)) { state = "ok"; note = "已创建"; }
                    if (id == "deps" && env != null && _env.IsValid(env)) { state = "ok"; note = "已同步"; }
                    if (id == "verify" && env != null && _env.IsValid(env)) { state = "ok"; note = "入口可用"; }
                }
            }
            Dictionary<string, object> d = new Dictionary<string, object>();
            d["id"] = id;
            d["label"] = label;
            d["short"] = shortName;
            d["hint"] = hint;
            d["state"] = state;
            d["note"] = note;
            return d;
        }

        private bool Updatable(EnvRecord env)
        {
            return env != null &&
                string.Equals(env.SourceKind, "git", StringComparison.OrdinalIgnoreCase) &&
                _tools.ResolveGit() != null;
        }

        private Dictionary<string, object> BuildVersion(EnvRecord env, bool refresh)
        {
            string currentRef = env == null ? "" : env.Ref;
            string sha = env == null ? "" : env.Sha;
            bool updatable = Updatable(env);
            Dictionary<string, object> result = new Dictionary<string, object>();
            List<object> versions = new List<object>();
            string latest = currentRef;
            string latestSha = sha;
            string mainSha = "";
            bool mainAhead = false;
            string error = "";
            if (updatable)
            {
                Dictionary<string, object> cache = EnsureVersions(refresh);
                error = Json.Str(cache, "error", "");
                mainSha = Json.Str(cache, "mainSha", "");
                List<object> tags = new List<object>();
                object[] tagArray = cache.ContainsKey("tags") ? cache["tags"] as object[] : null;
                if (tagArray != null) tags.AddRange(tagArray);
                string bestName = Json.Str(cache, "latest", "");
                string bestSha = Json.Str(cache, "latestSha", "");
                if (!string.IsNullOrEmpty(bestName)) { latest = bestName; latestSha = bestSha; }
                Dictionary<string, object> main = new Dictionary<string, object>();
                main["ref"] = "main";
                main["label"] = "main";
                main["kind"] = "branch";
                main["dev"] = true;
                main["sha"] = mainSha;
                main["short"] = ShortSha(mainSha);
                main["latest"] = false;
                main["current"] = !string.IsNullOrEmpty(sha) && string.Equals(sha, mainSha, StringComparison.OrdinalIgnoreCase);
                versions.Add(main);
                foreach (object item in tags)
                {
                    Dictionary<string, object> t = item as Dictionary<string, object>;
                    if (t == null) continue;
                    string name = Json.Str(t, "name", "");
                    string tagSha = Json.Str(t, "sha", "");
                    Dictionary<string, object> v = new Dictionary<string, object>();
                    v["ref"] = name;
                    v["label"] = name;
                    v["kind"] = "tag";
                    v["dev"] = false;
                    v["sha"] = tagSha;
                    v["short"] = ShortSha(tagSha);
                    v["latest"] = string.Equals(name, bestName, StringComparison.OrdinalIgnoreCase);
                    v["current"] = !string.IsNullOrEmpty(sha) && string.Equals(sha, tagSha, StringComparison.OrdinalIgnoreCase);
                    versions.Add(v);
                }
                mainAhead = string.Equals(currentRef, "main", StringComparison.OrdinalIgnoreCase) &&
                    !string.IsNullOrEmpty(mainSha) && !string.IsNullOrEmpty(sha) &&
                    !string.Equals(mainSha, sha, StringComparison.OrdinalIgnoreCase);
            }
            else
            {
                Dictionary<string, object> v = new Dictionary<string, object>();
                v["ref"] = string.IsNullOrEmpty(currentRef) ? _manifest.Base.Tag : currentRef;
                v["label"] = string.IsNullOrEmpty(currentRef) ? _manifest.Base.Tag : currentRef;
                v["kind"] = "pinned";
                v["dev"] = false;
                v["sha"] = sha;
                v["short"] = ShortSha(sha);
                v["latest"] = true;
                v["current"] = true;
                versions.Add(v);
                latest = Json.Str(v, "ref", _manifest.Base.Tag);
                latestSha = sha;
                error = env == null ? "尚未初始化" : "轻量安装不支持版本切换";
            }
            bool updateAvailable = !string.IsNullOrEmpty(sha) && !string.IsNullOrEmpty(latestSha) &&
                !string.Equals(sha, latestSha, StringComparison.OrdinalIgnoreCase) &&
                !string.Equals(currentRef, latest, StringComparison.OrdinalIgnoreCase) &&
                !string.Equals(latest, "main", StringComparison.OrdinalIgnoreCase);
            if (string.Equals(currentRef, "main", StringComparison.OrdinalIgnoreCase)) updateAvailable = mainAhead;
            result["current"] = currentRef;
            result["sha"] = ShortSha(sha);
            result["latest"] = latest;
            result["latestSha"] = latestSha;
            result["updateAvailable"] = updateAvailable;
            result["mainAhead"] = mainAhead;
            result["mainSha"] = mainSha;
            result["updatable"] = updatable;
            result["error"] = error;
            result["versions"] = versions;
            Dictionary<string, object> dirty = Dirty(false);
            result["dirty"] = Json.Int(dirty, "dirty", 0);
            result["dirtyTracked"] = Json.Int(dirty, "tracked", 0);
            result["dirtyUntracked"] = Json.Int(dirty, "untracked", 0);
            return result;
        }

        private Dictionary<string, object> EnsureVersions(bool refresh)
        {
            if (!refresh && _versionsCache != null && (DateTime.Now - _versionsAt).TotalSeconds < 120)
                return _versionsCache;
            Dictionary<string, object> result = new Dictionary<string, object>();
            try
            {
                Dictionary<string, string> map = _tools.GitLsRemote(_config.Repo, false, CancellationToken.None).GetAwaiter().GetResult();
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
                List<KeyValuePair<string, string>> ordered = tags.ToList();
                ordered.Sort(delegate(KeyValuePair<string, string> a, KeyValuePair<string, string> b)
                {
                    return VersionSortKey(b.Key).CompareTo(VersionSortKey(a.Key));
                });
                List<object> list = new List<object>();
                foreach (KeyValuePair<string, string> kv in ordered)
                {
                    Dictionary<string, object> t = new Dictionary<string, object>();
                    t["name"] = kv.Key;
                    t["sha"] = kv.Value;
                    list.Add(t);
                }
                result["ok"] = true;
                result["error"] = "";
                result["tags"] = list.ToArray();
                result["mainSha"] = map.ContainsKey("refs/heads/main") ? map["refs/heads/main"] : "";
                if (ordered.Count > 0)
                {
                    result["latest"] = ordered[0].Key;
                    result["latestSha"] = ordered[0].Value;
                }
                else
                {
                    result["latest"] = "";
                    result["latestSha"] = "";
                }
            }
            catch (Exception ex)
            {
                result["ok"] = false;
                result["error"] = "无法读取远端版本：" + ex.Message;
                result["tags"] = new object[0];
                result["mainSha"] = "";
                result["latest"] = "";
                result["latestSha"] = "";
            }
            _versionsCache = result;
            _versionsAt = DateTime.Now;
            return result;
        }

        private static string VersionSortKey(string name)
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

        private Dictionary<string, object> Dirty(bool force)
        {
            Dictionary<string, object> result = new Dictionary<string, object>();
            EnvRecord env = _env.Current;
            if (!Updatable(env))
            {
                result["ok"] = false;
                result["reason"] = "not-git";
                result["dirty"] = 0;
                result["tracked"] = 0;
                result["untracked"] = 0;
                result["sample"] = new string[0];
                return result;
            }
            string baseDir = env.ResolveBase(_paths);
            if (!force && (DateTime.Now - _dirtyAt).TotalSeconds < 30)
            {
                result["ok"] = true;
                result["dirty"] = CountDirty(_dirtyCache);
                result["tracked"] = CountTracked(_dirtyCache);
                result["untracked"] = CountUntracked(_dirtyCache);
                result["sample"] = SampleDirty(_dirtyCache);
                return result;
            }
            string status = _tools.GitStatus(baseDir);
            _dirtyCache = status;
            _dirtyAt = DateTime.Now;
            result["ok"] = true;
            result["dirty"] = CountDirty(status);
            result["tracked"] = CountTracked(status);
            result["untracked"] = CountUntracked(status);
            result["sample"] = SampleDirty(status);
            return result;
        }

        private static int CountDirty(string status)
        {
            if (string.IsNullOrEmpty(status)) return 0;
            return status.Split(new string[] { "\n" }, StringSplitOptions.RemoveEmptyEntries).Length;
        }

        private static int CountTracked(string status)
        {
            if (string.IsNullOrEmpty(status)) return 0;
            int n = 0;
            foreach (string line in status.Split(new string[] { "\n" }, StringSplitOptions.RemoveEmptyEntries))
                if (!line.StartsWith("??")) n++;
            return n;
        }

        private static int CountUntracked(string status)
        {
            if (string.IsNullOrEmpty(status)) return 0;
            int n = 0;
            foreach (string line in status.Split(new string[] { "\n" }, StringSplitOptions.RemoveEmptyEntries))
                if (line.StartsWith("??")) n++;
            return n;
        }

        private static string[] SampleDirty(string status)
        {
            if (string.IsNullOrEmpty(status)) return new string[0];
            string[] lines = status.Split(new string[] { "\n" }, StringSplitOptions.RemoveEmptyEntries);
            return lines.Take(20).Select(delegate(string s) { return s.Trim(); }).ToArray();
        }

        private Dictionary<string, object> BuildHealth(EnvRecord env, bool running)
        {
            List<object> checks = new List<object>();
            string uv = _tools.ResolveUv();
            AddCheck(checks, "uv", "uv 包管理器", uv != null ? "ok" : "fail", uv != null ? _tools.UvVersion() : "未找到");
            string python = env == null ? _tools.FindPython(_config.Python) : env.Python;
            AddCheck(checks, "python", "CPython", !string.IsNullOrEmpty(python) ? "ok" : (env == null ? "warn" : "fail"), string.IsNullOrEmpty(python) ? "未安装" : python);
            bool envValid = env != null && _env.IsValid(env);
            AddCheck(checks, "env", "当前环境", env == null ? "warn" : (envValid ? "ok" : "fail"), env == null ? "尚未初始化" : env.Id);
            AddCheck(checks, "entry", "sllkgui 入口", env == null ? "warn" : (envValid ? "ok" : "fail"), env == null ? "尚未初始化" : (envValid ? "可用" : "缺失"));
            bool useGit = env != null
                ? string.Equals(env.SourceKind, "git", StringComparison.OrdinalIgnoreCase)
                : _manifest.Profile(_config.Profile).UseGit;
            if (useGit)
            {
                string git = _tools.ResolveGit();
                AddCheck(checks, "git", "Git", git != null ? "ok" : "warn", git != null ? _tools.GitVersion() : "未安装");
            }
            long free = Util.GetFreeBytes(_paths.Runtime);
            string diskState = free < 0 ? "warn" : (free < 1024L * 1024 * 1024 ? "warn" : "ok");
            AddCheck(checks, "disk", "磁盘空间", diskState, free < 0 ? "无法读取" : Util.FormatBytes(free) + " 可用");

            bool fail = false;
            bool warn = false;
            foreach (object item in checks)
            {
                Dictionary<string, object> c = item as Dictionary<string, object>;
                if (c == null) continue;
                string s = Json.Str(c, "state", "");
                if (s == "fail") fail = true;
                if (s == "warn") warn = true;
            }
            string state;
            string message;
            if (env == null)
            {
                state = "warn";
                message = "尚未初始化，先完成初始化";
            }
            else if (fail)
            {
                state = "fail";
                message = "环境不完整，请初始化或修复";
            }
            else if (warn)
            {
                state = "warn";
                message = "环境可用，但存在需要注意的项";
            }
            else
            {
                state = "ok";
                message = "环境健康";
            }
            Dictionary<string, object> d = new Dictionary<string, object>();
            d["state"] = state;
            d["message"] = message;
            d["checks"] = checks;
            d["ready"] = envValid;
            d["running"] = running;
            return d;
        }

        private static void AddCheck(List<object> checks, string id, string label, string state, string note)
        {
            Dictionary<string, object> d = new Dictionary<string, object>();
            d["id"] = id;
            d["label"] = label;
            d["state"] = state;
            d["note"] = note;
            checks.Add(d);
        }

        private Dictionary<string, object> AppLog()
        {
            Dictionary<string, object> d = new Dictionary<string, object>();
            bool running = _app.IsRunning();
            List<string> lines = _app.AppLogLines(180);
            d["file"] = lines.Count > 0 ? Path.GetFileName(_app.LatestAppLog()) : "";
            d["lines"] = lines;
            d["running"] = running;
            d["notice"] = running ? "" : _app.AppExitNotice;
            return d;
        }

        private Dictionary<string, object> Diagnostics()
        {
            Dictionary<string, object> d = new Dictionary<string, object>();
            d["generatedAt"] = Util.NowIso();
            d["launcher"] = new Dictionary<string, object>
            {
                { "version", _manifest.LauncherVersion },
                { "signed", IsSigned() },
                { "exe", _paths.ExePath },
                { "runtime", _paths.Runtime },
                { "port", Port }
            };
            d["config"] = _config.ToDto(_manifest, _paths.Runtime, _manifest.LauncherVersion);
            d["env"] = _env.Current == null ? null : EnvDto(_env.Current);
            d["previous"] = _env.Previous == null ? null : _env.Previous.ToDto();
            d["versions"] = EnsureVersions(true);
            d["checks"] = BuildHealth(_env.Current, _app.IsRunning());
            List<object> logs = new List<object>();
            foreach (LogLine line in _log.Recent(80)) logs.Add(line.ToDto());
            d["logs"] = logs;
            d["appLog"] = _app.AppLogLines(80);
            d["appExitNotice"] = _app.AppExitNotice;
            d["os"] = new Dictionary<string, object>
            {
                { "version", Environment.OSVersion.VersionString },
                { "arch", Environment.GetEnvironmentVariable("PROCESSOR_ARCHITEW6432") ?? Environment.GetEnvironmentVariable("PROCESSOR_ARCHITECTURE") ?? "" },
                { "clr", Environment.Version.ToString() }
            };
            return d;
        }

        private bool IsSigned()
        {
            if (_signed.HasValue) return _signed.Value;
            bool signed = false;
            try
            {
                X509Certificate cert = X509Certificate.CreateFromSignedFile(_paths.ExePath);
                signed = cert != null;
            }
            catch { signed = false; }
            _signed = signed;
            return signed;
        }

        private static Dictionary<string, object> ParseBody(HttpRequest request)
        {
            try { return Json.ParseObject(request.Body); }
            catch { return new Dictionary<string, object>(); }
        }

        private static HttpResponse Ok()
        {
            return HttpResponse.Json(new Dictionary<string, object> { { "ok", true } });
        }

        private static HttpResponse Error(string message)
        {
            return HttpResponse.Json(new Dictionary<string, object> { { "ok", false }, { "error", message ?? "未知错误" } });
        }

        private static HttpResponse Forbidden()
        {
            HttpResponse r = HttpResponse.Json(new Dictionary<string, object> { { "ok", false }, { "error", "forbidden" } });
            r.Status = 403;
            return r;
        }

        private static string ShortSha(string sha)
        {
            if (string.IsNullOrEmpty(sha)) return "";
            return sha.Length <= 7 ? sha : sha.Substring(0, 7);
        }

        private static int QueryInt(string query, string key, int fallback)
        {
            string value = QueryValue(query, key);
            int parsed;
            return int.TryParse(value, out parsed) ? parsed : fallback;
        }

        private static bool QueryBool(string query, string key)
        {
            string value = QueryValue(query, key);
            return value == "1" || string.Equals(value, "true", StringComparison.OrdinalIgnoreCase);
        }

        private static string QueryValue(string query, string key)
        {
            if (string.IsNullOrEmpty(query)) return "";
            foreach (string part in query.Split('&'))
            {
                int idx = part.IndexOf('=');
                string name = idx >= 0 ? part.Substring(0, idx) : part;
                if (string.Equals(Uri.UnescapeDataString(name), key, StringComparison.OrdinalIgnoreCase))
                    return idx >= 0 ? Uri.UnescapeDataString(part.Substring(idx + 1)) : "";
            }
            return "";
        }
    }
}
