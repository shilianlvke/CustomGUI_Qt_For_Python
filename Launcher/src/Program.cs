using System;
using System.Collections.Generic;
using System.IO;
using System.Net.Sockets;
using System.Threading;
using System.Windows.Forms;

namespace SllkGui.Launcher
{
    internal static class Program
    {
        private static Mutex _mutex;

        [STAThread]
        private static int Main(string[] args)
        {
            bool selftest = false;
            bool printPlan = false;
            bool noBrowser = false;
            bool launchOnly = false;
            bool help = false;
            int port = 17823;
            string runtimeArg = "";

            for (int i = 0; i < args.Length; i++)
            {
                string a = args[i];
                if (a == "--selftest") selftest = true;
                else if (a == "--print-plan") printPlan = true;
                else if (a == "--no-browser") noBrowser = true;
                else if (a == "--launch") launchOnly = true;
                else if (a == "--help" || a == "-h" || a == "/?") help = true;
                else if (a == "--port" && i + 1 < args.Length) { int.TryParse(args[++i], out port); }
                else if (a == "--runtime" && i + 1 < args.Length) runtimeArg = args[++i];
                else
                {
                    if (!help) Console.Error.WriteLine("未知参数：" + a);
                    help = true;
                }
            }

            if (selftest || printPlan || help)
            {
                Util.AttachConsole();
                if (help)
                {
                    Console.WriteLine("SllkGui Launcher");
                    Console.WriteLine("  (无参数)        启动本地界面");
                    Console.WriteLine("  --launch        直接启动基座（不打开界面）");
                    Console.WriteLine("  --no-browser    不自动打开浏览器");
                    Console.WriteLine("  --port <n>      指定界面起始端口（默认 17823）");
                    Console.WriteLine("  --runtime <dir> 指定运行时目录");
                    Console.WriteLine("  --print-plan    打印安装计划（不下载）");
                    Console.WriteLine("  --selftest      运行内建自检");
                    return 0;
                }
                if (printPlan)
                {
                    try { return SelfTest.PrintPlan(); }
                    catch (Exception ex) { Console.Error.WriteLine("FAIL " + ex.Message); return 1; }
                }
                try { return SelfTest.Run(); }
                catch (Exception ex) { Console.Error.WriteLine("SELFTEST FAIL " + ex.Message); return 1; }
            }

            Application.EnableVisualStyles();
            try
            {
                Manifest manifest = Manifest.Load();
                LauncherPaths paths = LauncherPaths.Resolve(runtimeArg);
                paths.Ensure();
                LogBuffer log = new LogBuffer(Path.Combine(paths.Logs, "launcher.log"));
                Config config = Config.Load(paths.ConfigPath, manifest);

                bool primary = Acquire(paths);
                if (!primary)
                {
                    OpenExisting(paths, noBrowser);
                    return 0;
                }

                LauncherApp app = new LauncherApp(paths, manifest, config, log);
                if (launchOnly)
                {
                    Dictionary<string, object> result = app.LaunchOnly();
                    if (!Json.Bool(result, "ok", false))
                    {
                        string error = Json.Str(result, "error", "启动失败");
                        log.Err(error);
                        MessageBox.Show(error, "SllkGui 启动器", MessageBoxButtons.OK, MessageBoxIcon.Error);
                        return 1;
                    }
                    return 0;
                }

                app.Start(noBrowser, port);
                while (!app.ShutdownRequested) Thread.Sleep(300);
                app.Stop();
                return 0;
            }
            catch (Exception ex)
            {
                try
                {
                    LauncherPaths paths = LauncherPaths.Resolve(runtimeArg);
                    paths.Ensure();
                    File.AppendAllText(Path.Combine(paths.Logs, "launcher.log"),
                        DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + " [fatal] " + ex.ToString() + Environment.NewLine);
                }
                catch { }
                try { MessageBox.Show(ex.Message, "SllkGui 启动器启动失败", MessageBoxButtons.OK, MessageBoxIcon.Error); } catch { }
                return 1;
            }
            finally
            {
                Release();
            }
        }

        private static bool Acquire(LauncherPaths paths)
        {
            _mutex = new Mutex(false, "Local\\SllkGuiLauncher." + paths.RuntimeKey);
            return Wait(_mutex);
        }

        private static bool Wait(Mutex mutex)
        {
            try { return mutex.WaitOne(0); }
            catch (AbandonedMutexException) { return true; }
            catch { return false; }
        }

        private static void Release()
        {
            try { if (_mutex != null) _mutex.ReleaseMutex(); } catch { }
            try { if (_mutex != null) _mutex.Dispose(); } catch { }
        }

        private static void OpenExisting(LauncherPaths paths, bool noBrowser)
        {
            string url = "";
            for (int i = 0; i < 20; i++)
            {
                int port = ReadPort(paths);
                if (port > 0 && CanConnect(port))
                {
                    url = "http://127.0.0.1:" + port + "/";
                    break;
                }
                Thread.Sleep(250);
            }
            if (string.IsNullOrEmpty(url))
            {
                MessageBox.Show("已有启动器实例在运行，但无法连接它的界面（端口信息缺失或已失效）。请关闭其它启动器窗口后重试。",
                    "SllkGui 启动器", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }
            if (!noBrowser)
            {
                try { Util.OpenUrl(url); }
                catch
                {
                    MessageBox.Show("无法调用系统浏览器，请手动打开：\r\n" + url, "SllkGui 启动器", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                }
            }
        }

        private static int ReadPort(LauncherPaths paths)
        {
            try
            {
                if (File.Exists(paths.PortJsonPath))
                {
                    Dictionary<string, object> d = Json.ParseObject(File.ReadAllText(paths.PortJsonPath));
                    int port = Json.Int(d, "port", 0);
                    if (port > 0) return port;
                }
            }
            catch { }
            return 0;
        }

        private static bool CanConnect(int port)
        {
            try
            {
                using (TcpClient c = new TcpClient())
                {
                    IAsyncResult ar = c.BeginConnect("127.0.0.1", port, null, null);
                    if (!ar.AsyncWaitHandle.WaitOne(500)) return false;
                    c.EndConnect(ar);
                    return c.Connected;
                }
            }
            catch { return false; }
        }
    }
}
