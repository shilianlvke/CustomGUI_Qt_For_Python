using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace SllkGui.Launcher
{
    internal sealed class EnvRecord
    {
        public string Id = "";
        public string BasePath = "";
        public string VenvPath = "";
        public string Ref = "";
        public string Sha = "";
        public string Profile = "standard";
        public string SourceKind = "git";
        public string Python = "";
        public string Repo = "";
        public string CreatedAt = "";

        public string ResolveBase(LauncherPaths paths)
        {
            return paths.ResolvePath(BasePath);
        }

        public string ResolveVenv(LauncherPaths paths)
        {
            return paths.ResolvePath(VenvPath);
        }

        public string EntryPath(LauncherPaths paths)
        {
            return Path.Combine(ResolveVenv(paths), "Scripts", "sllkgui.exe");
        }

        public Dictionary<string, object> ToDto()
        {
            Dictionary<string, object> d = new Dictionary<string, object>();
            d["id"] = Id;
            d["basePath"] = BasePath;
            d["venvPath"] = VenvPath;
            d["ref"] = Ref;
            d["sha"] = Sha;
            d["profile"] = Profile;
            d["sourceKind"] = SourceKind;
            d["python"] = Python;
            d["repo"] = Repo;
            d["createdAt"] = CreatedAt;
            return d;
        }

        public static EnvRecord FromDto(Dictionary<string, object> d)
        {
            EnvRecord r = new EnvRecord();
            r.Id = Json.Str(d, "id", "");
            r.BasePath = Json.Str(d, "basePath", "");
            r.VenvPath = Json.Str(d, "venvPath", "");
            r.Ref = Json.Str(d, "ref", "");
            r.Sha = Json.Str(d, "sha", "");
            r.Profile = Json.Str(d, "profile", "standard");
            r.SourceKind = Json.Str(d, "sourceKind", "git");
            r.Python = Json.Str(d, "python", "");
            r.Repo = Json.Str(d, "repo", "");
            r.CreatedAt = Json.Str(d, "createdAt", "");
            return r;
        }
    }

    internal sealed class EnvManager
    {
        private readonly LauncherPaths _paths;
        private readonly Manifest _manifest;
        private readonly LogBuffer _log;

        public EnvRecord Current { get; private set; }
        public EnvRecord Previous { get; private set; }

        public EnvManager(LauncherPaths paths, Manifest manifest, LogBuffer log)
        {
            _paths = paths;
            _manifest = manifest;
            _log = log;
        }

        public void Load()
        {
            Current = ReadRecord(_paths.CurrentPath);
            Previous = ReadRecord(_paths.PreviousPath);
            if (Current != null && !IsValid(Current))
            {
                _log.Warn("当前环境记录不可用：" + Current.Id);
                Current = null;
            }
            if (Previous != null && !IsValid(Previous)) Previous = null;
        }

        public bool IsValid(EnvRecord record)
        {
            if (record == null) return false;
            string baseDir = record.ResolveBase(_paths);
            string entry = record.EntryPath(_paths);
            return Directory.Exists(baseDir) && File.Exists(entry);
        }

        private EnvRecord ReadRecord(string path)
        {
            try
            {
                if (!File.Exists(path)) return null;
                EnvRecord r = EnvRecord.FromDto(Json.ParseObject(File.ReadAllText(path)));
                return string.IsNullOrEmpty(r.Id) || string.IsNullOrEmpty(r.BasePath) ? null : r;
            }
            catch { return null; }
        }

        private void SaveRecord(string path, EnvRecord record)
        {
            Util.AtomicWriteAllText(path, Json.Stringify(record.ToDto()));
        }

        public void SetCurrent(EnvRecord record)
        {
            if (record == null) throw new ArgumentNullException("record");
            EnvRecord old = Current;
            if (old != null && !string.Equals(old.Id, record.Id, StringComparison.OrdinalIgnoreCase))
            {
                Previous = old;
                SaveRecord(_paths.PreviousPath, old);
            }
            Current = record;
            SaveRecord(_paths.CurrentPath, record);
            WriteMeta(record);
        }

        public void WriteMeta(EnvRecord record)
        {
            try
            {
                string dir = Path.Combine(_paths.EnvRoot, Util.SanitizeId(record.Id));
                Directory.CreateDirectory(dir);
                Util.AtomicWriteAllText(Path.Combine(dir, "meta.json"), Json.Stringify(record.ToDto()));
            }
            catch { }
        }

        public bool SwitchTo(EnvRecord record)
        {
            if (record == null || !IsValid(record)) return false;
            SetCurrent(record);
            return true;
        }

        public bool Rollback()
        {
            if (Previous == null || !IsValid(Previous)) return false;
            EnvRecord target = Previous;
            Previous = Current;
            Current = target;
            SaveRecord(_paths.CurrentPath, Current);
            if (Previous != null) SaveRecord(_paths.PreviousPath, Previous);
            return true;
        }

        public List<EnvRecord> List()
        {
            List<EnvRecord> list = new List<EnvRecord>();
            Dictionary<string, EnvRecord> seen = new Dictionary<string, EnvRecord>(StringComparer.OrdinalIgnoreCase);
            if (Current != null) seen[Current.Id] = Current;
            if (Previous != null) seen[Previous.Id] = Previous;
            try
            {
                if (Directory.Exists(_paths.EnvRoot))
                {
                    foreach (string dir in Directory.GetDirectories(_paths.EnvRoot))
                    {
                        string meta = Path.Combine(dir, "meta.json");
                        if (!File.Exists(meta)) continue;
                        EnvRecord r = EnvRecord.FromDto(Json.ParseObject(File.ReadAllText(meta)));
                        if (!string.IsNullOrEmpty(r.Id) && !seen.ContainsKey(r.Id)) seen[r.Id] = r;
                    }
                }
            }
            catch { }
            list.AddRange(seen.Values);
            return list;
        }

        public long DiskBytes(EnvRecord record)
        {
            if (record == null) return 0;
            return Util.DirectorySize(record.ResolveBase(_paths));
        }

        public Dictionary<string, object> Cleanup()
        {
            long freed = 0;
            int removed = 0;
            List<EnvRecord> all = List();
            _log.Sys("清理：环境 " + all.Count + " 个");
            foreach (EnvRecord r in all)
            {
                if (r == null) continue;
                if (Current != null && string.Equals(r.Id, Current.Id, StringComparison.OrdinalIgnoreCase)) continue;
                if (Previous != null && string.Equals(r.Id, Previous.Id, StringComparison.OrdinalIgnoreCase)) continue;
                string dir = Path.Combine(_paths.EnvRoot, Util.SanitizeId(r.Id));
                _log.Sys("清理：删除旧环境 " + r.Id);
                long size = Util.DirectorySize(dir);
                Util.TryDeleteDirectory(dir);
                if (!Directory.Exists(dir))
                {
                    freed += size;
                    removed++;
                    _log.Ok("清理：已删除 " + r.Id + " · " + Util.FormatBytes(size));
                }
            }
            // 只清 cache 根目录的下载包，保留 uv 缓存（大量硬链接，删除慢且会影响下次安装速度）。
            long cacheFreed = 0;
            _log.Sys("清理：检查下载缓存");
            try
            {
                Directory.CreateDirectory(_paths.Cache);
                foreach (string file in Directory.GetFiles(_paths.Cache))
                {
                    long size = 0;
                    try { size = new FileInfo(file).Length; } catch { }
                    Util.TryDeleteFile(file);
                    if (!File.Exists(file)) cacheFreed += size;
                }
            }
            catch { }
            freed += cacheFreed;
            Dictionary<string, object> d = new Dictionary<string, object>();
            d["ok"] = true;
            d["removedEnvs"] = removed;
            d["freedBytes"] = freed;
            d["freedText"] = Util.FormatBytes(freed);
            return d;
        }

        public EnvRecord Create(string id, string basePath, string venvPath, string refName, string sha, string profile, string sourceKind, string python, string repo)
        {
            EnvRecord r = new EnvRecord();
            r.Id = Util.SanitizeId(id);
            r.BasePath = basePath;
            r.VenvPath = venvPath;
            r.Ref = refName;
            r.Sha = sha;
            r.Profile = profile;
            r.SourceKind = sourceKind;
            r.Python = python;
            r.Repo = repo;
            r.CreatedAt = Util.NowIso();
            return r;
        }
    }
}
