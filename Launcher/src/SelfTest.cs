using System;
using System.Collections.Generic;
using System.IO;
using System.Net.Http;
using System.Text;
using System.Threading;

namespace SllkGui.Launcher
{
    internal static class SelfTest
    {
        public static int PrintPlan()
        {
            Manifest m = Manifest.Load();
            Console.WriteLine("SllkGui Launcher " + m.LauncherVersion + " 安装计划");
            Console.WriteLine("  repo      : " + m.Repo);
            Console.WriteLine("  uv        : " + m.Uv.Version + "  sha256=" + Short(m.Uv.Sha256X64));
            Console.WriteLine("  python    : " + m.Python.Version + "  (由 uv 校验下载)");
            Console.WriteLine("  mingit    : " + m.MiniGit.Version + "  sha256=" + Short(m.MiniGit.Sha256));
            Console.WriteLine("  base      : " + m.Base.Tag + "  sha=" + Short(m.Base.Sha));
            foreach (ProfileInfo p in m.Profiles)
            {
                Console.WriteLine("  profile   : " + p.Name + " (" + p.Label + ")  download≈" + p.DownloadMb + "MB  installed≈" + p.InstalledMb + "MB  git=" + p.UseGit + " addons=" + p.IncludeAddons);
            }
            ProfileInfo standard = m.Profile("standard");
            Console.WriteLine("  first run : " + m.Uv.Version + " -> " + m.Python.Version + " -> MinGit -> git clone -> venv -> uv sync");
            Console.WriteLine("  runtime   : %USERPROFILE%\\.SllkGui（当前用户目录）");
            return 0;
        }

        public static int Run()
        {
            // 自检临时数据同样放入当前用户目录，不写启动器所在目录。
            string userHome = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
            if (string.IsNullOrEmpty(userHome))
                userHome = Environment.GetEnvironmentVariable("USERPROFILE");
            string temp = Path.Combine(userHome, ".SllkGui", ".selftest-" + Guid.NewGuid().ToString("N"));
            LauncherApp app = null;
            int failures = 0;
            try
            {
                Directory.CreateDirectory(temp);
                Manifest manifest = Manifest.Load();
                Check(true, "内嵌 manifest 可加载 · " + manifest.LauncherVersion);
                LauncherPaths paths = LauncherPaths.Resolve(temp);
                paths.Ensure();
                LogBuffer log = new LogBuffer(Path.Combine(paths.Logs, "selftest.log"));

                // 1. 旧配置不兼容：直接丢弃并重建默认 schema v2
                File.WriteAllText(paths.ConfigPath,
                    "{\"mirror\":\"global\",\"repo\":\"https://gitee.com/shilianlvke/SllkGui.git\",\"mode\":\"gallery\"}",
                    new UTF8Encoding(false));
                Config config = Config.Load(paths.ConfigPath, manifest);
                Check(config.SchemaVersion == 2, "旧配置被丢弃并重建为 schema v2");
                Check(config.Mirror == "cn", "旧配置 mirror 不保留，回到默认国内镜像");
                Check(config.Mode == "run", "旧配置 mode 不保留，回到默认正式模式");
                Check(config.Profile == "standard", "默认 profile=standard");
                config.Save(paths.ConfigPath);
                Config again = Config.Load(paths.ConfigPath, manifest);
                Check(again.Mirror == "cn" && again.Mode == "run", "默认配置可持久化");

                // 2. 旧 runtime 不兼容：不扫描 runtime\base，不接管
                string oldBase = Path.Combine(paths.Runtime, "base");
                Directory.CreateDirectory(Path.Combine(oldBase, ".venv", "Scripts"));
                File.WriteAllText(Path.Combine(oldBase, ".venv", "Scripts", "sllkgui.exe"), "");
                File.WriteAllText(Path.Combine(paths.Runtime, "base-ref.json"),
                    "{\"ref\":\"base-v4.0.2\",\"sha\":\"ecb60018464284c843e8f304eff16678c22a15b6\"}");
                EnvManager env = new EnvManager(paths, manifest, log);
                env.Load();
                Check(env.Current == null, "旧 runtime 不再被接管");

                // 3. HTTP + security
                app = new LauncherApp(paths, manifest, config, log);
                app.Start(true, 0);
                string baseUrl = "http://127.0.0.1:" + app.Port;
                using (HttpClient client = new HttpClient())
                {
                    client.BaseAddress = new Uri(baseUrl);
                    HttpResponseMessage page = client.GetAsync("/").GetAwaiter().GetResult();
                    string html = page.Content.ReadAsStringAsync().GetAwaiter().GetResult();
                    Check(page.StatusCode == System.Net.HttpStatusCode.OK, "GET / 返回 200");
                    Check(html.IndexOf("SllkGui", StringComparison.OrdinalIgnoreCase) >= 0, "GET / 返回内嵌 UI");
                    Check(page.Headers.Contains("X-Frame-Options"), "GET / 带 X-Frame-Options");
                    Check(page.Headers.Contains("Content-Security-Policy"), "GET / 带 CSP");

                    HttpResponseMessage noToken = client.GetAsync("/api/state").GetAwaiter().GetResult();
                    Check((int)noToken.StatusCode == 403, "无 token 的 /api/state 返回 403");

                    HttpRequestMessage stateReq = new HttpRequestMessage(HttpMethod.Get, "/api/state");
                    stateReq.Headers.Add("X-Token", app.Token);
                    HttpResponseMessage state = client.SendAsync(stateReq).GetAwaiter().GetResult();
                    string stateBody = state.Content.ReadAsStringAsync().GetAwaiter().GetResult();
                    Check((int)state.StatusCode == 200, "带 token 的 /api/state 返回 200");
                    Check(stateBody.IndexOf("\"phase\"", StringComparison.Ordinal) >= 0, "/api/state 返回 phase");

                    HttpRequestMessage evilHost = new HttpRequestMessage(HttpMethod.Get, "/");
                    evilHost.Headers.Host = "evil.example";
                    HttpResponseMessage denied = client.SendAsync(evilHost).GetAwaiter().GetResult();
                    Check((int)denied.StatusCode == 403, "非法 Host 被拒绝");

                    HttpRequestMessage evilOrigin = new HttpRequestMessage(HttpMethod.Post, "/api/config");
                    evilOrigin.Headers.Add("X-Token", app.Token);
                    evilOrigin.Headers.Add("Origin", "http://evil.example");
                    evilOrigin.Content = new StringContent("{}", Encoding.UTF8, "application/json");
                    HttpResponseMessage originDenied = client.SendAsync(evilOrigin).GetAwaiter().GetResult();
                    Check((int)originDenied.StatusCode == 403, "非法 Origin 被拒绝");

                    HttpRequestMessage small = new HttpRequestMessage(HttpMethod.Post, "/api/config");
                    small.Headers.Add("X-Token", app.Token);
                    small.Content = new StringContent("{\"mirror\":\"global\"}", Encoding.UTF8, "application/json");
                    HttpResponseMessage smallResp = client.SendAsync(small).GetAwaiter().GetResult();
                    Check((int)smallResp.StatusCode == 200, "小 POST body（header/body 同包）返回 200");

                    HttpRequestMessage big = new HttpRequestMessage(HttpMethod.Post, "/api/config");
                    big.Headers.Add("X-Token", app.Token);
                    big.Headers.ExpectContinue = false;
                    big.Content = new StringContent("{\"x\":\"" + new string('a', 1100000) + "\"}", Encoding.UTF8, "application/json");
                    HttpResponseMessage tooLarge = client.SendAsync(big).GetAwaiter().GetResult();
                    Check((int)tooLarge.StatusCode == 413, "超大请求体返回 413");

                    HttpRequestMessage missing = new HttpRequestMessage(HttpMethod.Get, "/api/nope");
                    missing.Headers.Add("X-Token", app.Token);
                    HttpResponseMessage notFound = client.SendAsync(missing).GetAwaiter().GetResult();
                    Check((int)notFound.StatusCode == 404, "未知 API 返回 404");
                }
                Console.WriteLine("SELFTEST PASS");
                return 0;
            }
            catch (Exception ex)
            {
                failures++;
                Console.WriteLine("SELFTEST FAIL " + ex.GetType().Name + ": " + ex.Message);
                return 1;
            }
            finally
            {
                try { if (app != null) app.Stop(); } catch { }
                try { if (Directory.Exists(temp)) Directory.Delete(temp, true); } catch { }
                if (failures > 0) Console.WriteLine("SELFTEST RESULT: FAIL");
            }
        }

        private static void Check(bool condition, string label)
        {
            if (condition) Console.WriteLine("PASS  " + label);
            else
            {
                Console.WriteLine("FAIL  " + label);
                throw new InvalidOperationException(label);
            }
        }

        private static string Short(string value)
        {
            if (string.IsNullOrEmpty(value)) return "";
            return value.Length <= 16 ? value : value.Substring(0, 16) + "…";
        }
    }
}
