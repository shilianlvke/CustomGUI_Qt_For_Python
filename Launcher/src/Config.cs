using System;
using System.Collections.Generic;
using System.IO;
using System.Text.RegularExpressions;

namespace SllkGui.Launcher
{
    internal sealed class Config
    {
        public int SchemaVersion = 2;
        public string Mirror = "cn";
        public string Repo = "";
        public string Branch = "main";
        public string Python = "3.12.16";
        public string Mode = "run";
        public string Profile = "standard";
        public bool AutoLaunch = false;
        public bool CloseWithPage = true;
        public bool SafeMode = false;
        public bool NoPluginDeps = false;

        public static Config Default(Manifest manifest)
        {
            Config c = new Config();
            c.Repo = manifest.Repo;
            c.Branch = manifest.DefaultBranch;
            c.Python = manifest.Python.Version;
            c.Profile = manifest.Profile("standard").Name;
            return c;
        }

        public static Config Load(string path, Manifest manifest)
        {
            Config c = Default(manifest);
            if (!File.Exists(path))
            {
                c.Save(path);
                return c;
            }
            try
            {
                Dictionary<string, object> d = Json.ParseObject(File.ReadAllText(path));
                // 只接受当前 schema；旧配置直接丢弃并重建，不做迁移。
                if (Json.Int(d, "schemaVersion", 0) != 2)
                {
                    c.Save(path);
                    return c;
                }
                c.SchemaVersion = 2;
                c.Mirror = Json.Str(d, "mirror", c.Mirror);
                c.Repo = Json.Str(d, "repo", c.Repo);
                c.Branch = Json.Str(d, "branch", c.Branch);
                c.Python = Json.Str(d, "python", c.Python);
                c.Mode = Json.Str(d, "mode", c.Mode);
                c.Profile = Json.Str(d, "profile", c.Profile);
                c.AutoLaunch = Json.Bool(d, "autoLaunch", c.AutoLaunch);
                c.CloseWithPage = Json.Bool(d, "closeWithPage", c.CloseWithPage);
                c.SafeMode = Json.Bool(d, "safeMode", c.SafeMode);
                c.NoPluginDeps = Json.Bool(d, "noPluginDeps", c.NoPluginDeps);
            }
            catch
            {
                c.Save(path);
                return c;
            }
            bool changed = c.Normalize(manifest);
            if (changed) c.Save(path);
            return c;
        }

        public void Save(string path)
        {
            Dictionary<string, object> d = new Dictionary<string, object>();
            d["schemaVersion"] = 2;
            d["mirror"] = Mirror;
            d["repo"] = Repo;
            d["branch"] = Branch;
            d["python"] = Python;
            d["mode"] = Mode;
            d["profile"] = Profile;
            d["autoLaunch"] = AutoLaunch;
            d["closeWithPage"] = CloseWithPage;
            d["safeMode"] = SafeMode;
            d["noPluginDeps"] = NoPluginDeps;
            Util.AtomicWriteAllText(path, Json.Stringify(d));
        }

        public bool Normalize(Manifest manifest)
        {
            bool changed = false;
            string mirror = string.Equals(Mirror, "global", StringComparison.OrdinalIgnoreCase) ? "global" : "cn";
            if (mirror != Mirror) { Mirror = mirror; changed = true; }
            string mode = string.Equals(Mode, "gallery", StringComparison.OrdinalIgnoreCase) ? "gallery" : "run";
            if (mode != Mode) { Mode = mode; changed = true; }
            if (!IsKnownProfile(Profile, manifest)) { Profile = manifest.Profile("standard").Name; changed = true; }
            if (!IsAllowedRepo(Repo)) { Repo = manifest.Repo; changed = true; }
            if (!IsValidBranch(Branch)) { Branch = manifest.DefaultBranch; changed = true; }
            if (!IsValidPython(Python)) { Python = manifest.Python.Version; changed = true; }
            return changed;
        }

        public static bool IsKnownProfile(string name, Manifest manifest)
        {
            foreach (ProfileInfo p in manifest.Profiles)
                if (string.Equals(p.Name, name, StringComparison.OrdinalIgnoreCase)) return true;
            return false;
        }

        public static bool IsAllowedRepo(string repo)
        {
            Uri uri;
            if (!Uri.TryCreate(repo, UriKind.Absolute, out uri)) return false;
            if (uri.Scheme != Uri.UriSchemeHttps) return false;
            string host = uri.Host.ToLowerInvariant();
            return host == "gitee.com" || host == "github.com" || host == "www.github.com";
        }

        public static bool IsValidBranch(string branch)
        {
            return !string.IsNullOrEmpty(branch) && Regex.IsMatch(branch, "^[A-Za-z0-9][A-Za-z0-9._\\-]*$") && branch.Length <= 120;
        }

        public static bool IsValidPython(string version)
        {
            return !string.IsNullOrEmpty(version) && Regex.IsMatch(version, "^\\d+\\.\\d+(\\.\\d+)?$");
        }

        public Dictionary<string, object> ToDto(Manifest manifest, string runtime, string launcherVersion)
        {
            ProfileInfo profile = manifest.Profile(Profile);
            Dictionary<string, object> d = new Dictionary<string, object>();
            d["schemaVersion"] = SchemaVersion;
            d["mirror"] = Mirror;
            d["mirrorLabel"] = manifest.Mirror(Mirror).Label;
            d["repo"] = Repo;
            d["branch"] = Branch;
            d["python"] = Python;
            d["mode"] = Mode;
            d["modeLabel"] = Mode == "gallery" ? "预览模式" : "正式模式";
            d["profile"] = profile.Name;
            d["profileLabel"] = profile.Label;
            d["profileDescription"] = profile.Description;
            d["useGit"] = profile.UseGit;
            d["includeAddons"] = profile.IncludeAddons;
            d["downloadMb"] = profile.DownloadMb;
            d["installedMb"] = profile.InstalledMb;
            d["autoLaunch"] = AutoLaunch;
            d["closeWithPage"] = CloseWithPage;
            d["safeMode"] = SafeMode;
            d["noPluginDeps"] = NoPluginDeps;
            d["runtime"] = runtime;
            d["launcherVersion"] = launcherVersion;
            return d;
        }

        public string ApplyDto(Dictionary<string, object> body, Manifest manifest)
        {
            if (body == null) return "缺少请求内容";
            if (body.ContainsKey("mirror"))
            {
                string mirror = Json.Str(body, "mirror", Mirror);
                if (mirror != "cn" && mirror != "global") return "镜像源参数不合法";
                Mirror = mirror;
            }
            if (body.ContainsKey("mode"))
            {
                string mode = Json.Str(body, "mode", Mode);
                if (mode != "run" && mode != "gallery") return "模式参数不合法";
                Mode = mode;
            }
            if (body.ContainsKey("profile"))
            {
                string profile = Json.Str(body, "profile", Profile);
                if (!IsKnownProfile(profile, manifest)) return "安装配置不合法";
                Profile = manifest.Profile(profile).Name;
            }
            if (body.ContainsKey("autoLaunch")) AutoLaunch = Json.Bool(body, "autoLaunch", AutoLaunch);
            if (body.ContainsKey("closeWithPage")) CloseWithPage = Json.Bool(body, "closeWithPage", CloseWithPage);
            if (body.ContainsKey("safeMode")) SafeMode = Json.Bool(body, "safeMode", SafeMode);
            if (body.ContainsKey("noPluginDeps")) NoPluginDeps = Json.Bool(body, "noPluginDeps", NoPluginDeps);
            Normalize(manifest);
            return "";
        }
    }
}
