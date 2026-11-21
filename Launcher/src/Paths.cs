using System;
using System.IO;
using System.Reflection;

namespace SllkGui.Launcher
{
    internal sealed class LauncherPaths
    {
        public string ExePath { get; private set; }
        public string Root { get; private set; }
        public string Runtime { get; private set; }
        public string EnvRoot { get; private set; }
        public string Tools { get; private set; }
        public string UvDir { get; private set; }
        public string GitDir { get; private set; }
        public string PythonDir { get; private set; }
        public string DataDir { get; private set; }
        public string Logs { get; private set; }
        public string Cache { get; private set; }
        public string UvCache { get; private set; }
        public string ConfigPath { get; private set; }
        public string CurrentPath { get; private set; }
        public string PreviousPath { get; private set; }
        public string PortJsonPath { get; private set; }
        public string AppJsonPath { get; private set; }
        public string RuntimeKey { get; private set; }

        private LauncherPaths() { }

        public static LauncherPaths Resolve()
        {
            return Resolve(null);
        }

        public static LauncherPaths Resolve(string runtimeOverride)
        {
            LauncherPaths p = new LauncherPaths();
            p.ExePath = Assembly.GetExecutingAssembly().Location;
            p.Root = Path.GetDirectoryName(p.ExePath);

            string runtime = runtimeOverride;
            if (string.IsNullOrEmpty(runtime))
            {
                string portable = Path.Combine(p.Root, "runtime");
                string local = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "SllkGuiLauncher");
                runtime = portable;
                try
                {
                    Directory.CreateDirectory(portable);
                    string probe = Path.Combine(portable, ".probe-" + Guid.NewGuid().ToString("N"));
                    File.WriteAllText(probe, "1");
                    File.Delete(probe);
                }
                catch
                {
                    runtime = local;
                }
            }
            p.Runtime = Path.GetFullPath(runtime);
            p.EnvRoot = Path.Combine(runtime, "envs");
            p.Tools = Path.Combine(runtime, "tools");
            p.UvDir = Path.Combine(p.Tools, "uv");
            p.GitDir = Path.Combine(p.Tools, "git");
            p.PythonDir = Path.Combine(p.Tools, "python");
            p.DataDir = Path.Combine(runtime, "data");
            p.Logs = Path.Combine(runtime, "logs");
            p.Cache = Path.Combine(runtime, "cache");
            p.UvCache = Path.Combine(p.Cache, "uv");
            p.ConfigPath = Path.Combine(runtime, "config.json");
            p.CurrentPath = Path.Combine(runtime, "current.json");
            p.PreviousPath = Path.Combine(runtime, "previous.json");
            p.PortJsonPath = Path.Combine(runtime, "port.json");
            p.AppJsonPath = Path.Combine(runtime, "app.json");
            p.RuntimeKey = Util.Md5Hex(runtime.ToLowerInvariant()).Substring(0, 12);
            return p;
        }

        public void Ensure()
        {
            Directory.CreateDirectory(Runtime);
            Directory.CreateDirectory(EnvRoot);
            Directory.CreateDirectory(Tools);
            Directory.CreateDirectory(DataDir);
            Directory.CreateDirectory(Logs);
            Directory.CreateDirectory(Cache);
            Directory.CreateDirectory(UvCache);
        }

        public string ResolvePath(string relative)
        {
            return Util.ResolveRelative(Runtime, relative);
        }
    }
}
