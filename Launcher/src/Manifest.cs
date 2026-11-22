using System;
using System.Collections.Generic;

namespace SllkGui.Launcher
{
    internal sealed class BaseInfo
    {
        public string Tag;
        public string Sha;
    }

    internal sealed class UvInfo
    {
        public string Version;
        public string AssetX64;
        public string Sha256X64;
        public long BytesX64;
        public string AssetArm64;
        public string Sha256Arm64;
        public long BytesArm64;
    }

    internal sealed class MiniGitInfo
    {
        public string Version;
        public string Asset;
        public string Sha256;
        public long Bytes;
    }

    internal sealed class PythonInfo
    {
        public string Version;
        public string Tag;
        public string Sha256;
    }

    internal sealed class ProfileInfo
    {
        public string Name;
        public string Label;
        public bool UseGit;
        public bool IncludeAddons;
        public int DownloadMb;
        public int InstalledMb;
        public string Description;
    }

    internal sealed class MirrorInfo
    {
        public string Mode;
        public string Label;
        public string Pypi;
        public string Github;
        public string Python;
        public string GitBinary;
    }

    internal sealed class Manifest
    {
        public int ManifestVersion;
        public string LauncherVersion;
        public string Repo;
        public string RepoWeb;
        public string DefaultBranch;
        public BaseInfo Base;
        public UvInfo Uv;
        public MiniGitInfo MiniGit;
        public PythonInfo Python;
        public List<ProfileInfo> Profiles = new List<ProfileInfo>();
        public Dictionary<string, MirrorInfo> Mirrors = new Dictionary<string, MirrorInfo>(StringComparer.OrdinalIgnoreCase);

        public static Manifest Load()
        {
            string text = Resources.ReadText("Launcher.manifest.json");
            Dictionary<string, object> root = Json.ParseObject(text);
            Manifest m = new Manifest();
            m.ManifestVersion = Json.Int(root, "manifestVersion", 2);
            m.LauncherVersion = Json.Str(root, "launcherVersion", "5.0.0");
            m.Repo = Json.Str(root, "repo", "https://gitee.com/shilianlvke/SllkGui.git");
            m.RepoWeb = Json.Str(root, "repoWeb", "https://gitee.com/shilianlvke/SllkGui");
            m.DefaultBranch = Json.Str(root, "defaultBranch", "main");

            Dictionary<string, object> b = Json.Dict(root, "base");
            m.Base = new BaseInfo();
            m.Base.Tag = Json.Str(b, "tag", "base-v4.1.0");
            m.Base.Sha = Json.Str(b, "sha", "");

            Dictionary<string, object> u = Json.Dict(root, "uv");
            m.Uv = new UvInfo();
            m.Uv.Version = Json.Str(u, "version", "0.13.9");
            m.Uv.AssetX64 = Json.Str(u, "assetX64", "uv-x86_64-pc-windows-msvc.zip");
            m.Uv.Sha256X64 = Json.Str(u, "sha256X64", "");
            m.Uv.BytesX64 = Json.Long(u, "bytesX64", 0);
            m.Uv.AssetArm64 = Json.Str(u, "assetArm64", "uv-aarch64-pc-windows-msvc.zip");
            m.Uv.Sha256Arm64 = Json.Str(u, "sha256Arm64", "");
            m.Uv.BytesArm64 = Json.Long(u, "bytesArm64", 0);

            Dictionary<string, object> g = Json.Dict(root, "minGit");
            m.MiniGit = new MiniGitInfo();
            m.MiniGit.Version = Json.Str(g, "version", "2.56.1");
            m.MiniGit.Asset = Json.Str(g, "asset", "MinGit-2.56.1-64-bit.zip");
            m.MiniGit.Sha256 = Json.Str(g, "sha256", "");
            m.MiniGit.Bytes = Json.Long(g, "bytes", 0);

            Dictionary<string, object> p = Json.Dict(root, "python");
            m.Python = new PythonInfo();
            m.Python.Version = Json.Str(p, "version", "3.12.16");
            m.Python.Tag = Json.Str(p, "tag", "20261110");
            m.Python.Sha256 = Json.Str(p, "sha256", "");

            foreach (object item in Json.List(root, "profiles"))
            {
                Dictionary<string, object> d = item as Dictionary<string, object>;
                if (d == null) continue;
                ProfileInfo info = new ProfileInfo();
                info.Name = Json.Str(d, "name", "standard");
                info.Label = Json.Str(d, "label", info.Name);
                info.UseGit = Json.Bool(d, "useGit", true);
                info.IncludeAddons = Json.Bool(d, "includeAddons", false);
                info.DownloadMb = Json.Int(d, "downloadMb", 176);
                info.InstalledMb = Json.Int(d, "installedMb", 530);
                info.Description = Json.Str(d, "description", "");
                m.Profiles.Add(info);
            }
            if (m.Profiles.Count == 0)
            {
                m.Profiles.Add(new ProfileInfo { Name = "standard", Label = "标准", UseGit = true, IncludeAddons = false, DownloadMb = 176, InstalledMb = 530 });
            }

            Dictionary<string, object> mirrors = Json.Dict(root, "mirrors");
            foreach (string mode in new string[] { "cn", "global" })
            {
                Dictionary<string, object> md = Json.Dict(mirrors, mode);
                MirrorInfo mi = new MirrorInfo();
                mi.Mode = mode;
                mi.Label = Json.Str(md, "label", mode == "cn" ? "国内镜像" : "官方源");
                mi.Pypi = Json.Str(md, "pypi", mode == "cn" ? "https://pypi.tuna.tsinghua.edu.cn/simple" : "https://pypi.org/simple");
                mi.Github = Json.Str(md, "github", mode == "cn" ? "https://gh-proxy.com/https://github.com" : "https://github.com");
                mi.Python = Json.Str(md, "python", mode == "cn" ? "https://gh-proxy.com/https://github.com/astral-sh/python-build-standalone/releases/download" : "https://github.com/astral-sh/python-build-standalone/releases/download");
                mi.GitBinary = Json.Str(md, "gitBinary", mode == "cn" ? "https://registry.npmmirror.com/-/binary/git-for-windows/" : "https://github.com/git-for-windows/git/releases/download");
                m.Mirrors[mode] = mi;
            }
            return m;
        }

        public ProfileInfo Profile(string name)
        {
            foreach (ProfileInfo p in Profiles)
                if (string.Equals(p.Name, name, StringComparison.OrdinalIgnoreCase)) return p;
            return Profiles[0];
        }

        public MirrorInfo Mirror(string mode)
        {
            MirrorInfo m;
            if (Mirrors.TryGetValue(mode ?? "cn", out m)) return m;
            return Mirrors["cn"];
        }

        public bool IsArm64()
        {
            string arch = Environment.GetEnvironmentVariable("PROCESSOR_ARCHITEW6432");
            if (string.IsNullOrEmpty(arch)) arch = Environment.GetEnvironmentVariable("PROCESSOR_ARCHITECTURE");
            return string.Equals(arch, "ARM64", StringComparison.OrdinalIgnoreCase);
        }

        public string UvAsset()
        {
            return IsArm64() ? Uv.AssetArm64 : Uv.AssetX64;
        }

        public string UvSha256()
        {
            return IsArm64() ? Uv.Sha256Arm64 : Uv.Sha256X64;
        }

        public long UvBytes()
        {
            return IsArm64() ? Uv.BytesArm64 : Uv.BytesX64;
        }

        public List<string> UvUrls(MirrorInfo mirror)
        {
            List<string> urls = new List<string>();
            string suffix = "/astral-sh/uv/releases/download/" + Uv.Version + "/" + UvAsset();
            urls.Add(mirror.Github.TrimEnd('/') + suffix);
            string official = "https://github.com" + suffix;
            if (!urls.Contains(official)) urls.Add(official);
            return urls;
        }

        public List<string> MiniGitUrls(MirrorInfo mirror)
        {
            List<string> urls = new List<string>();
            string suffix = "/v" + MiniGit.Version + ".windows.1/" + MiniGit.Asset;
            if (string.Equals(mirror.Mode, "cn", StringComparison.OrdinalIgnoreCase))
                urls.Add(mirror.GitBinary.TrimEnd('/') + suffix);
            string proxied = mirror.Github.TrimEnd('/') + "/git-for-windows/git/releases/download" + suffix;
            if (!urls.Contains(proxied)) urls.Add(proxied);
            string official = "https://github.com/git-for-windows/git/releases/download" + suffix;
            if (!urls.Contains(official)) urls.Add(official);
            return urls;
        }
    }
}
