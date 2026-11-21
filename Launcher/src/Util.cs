using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Threading;

namespace SllkGui.Launcher
{
    internal static class Util
    {
        public static string Quote(string value)
        {
            if (value == null) return "\"\"";
            if (value.Length > 0 && value.IndexOfAny(new char[] { ' ', '\t', '\n', '\v', '"' }) < 0) return value;
            StringBuilder sb = new StringBuilder();
            sb.Append('"');
            int backslashes = 0;
            foreach (char c in value)
            {
                if (c == '\\')
                {
                    backslashes++;
                }
                else if (c == '"')
                {
                    sb.Append('\\', backslashes * 2 + 1);
                    sb.Append('"');
                    backslashes = 0;
                }
                else
                {
                    if (backslashes > 0) sb.Append('\\', backslashes);
                    backslashes = 0;
                    sb.Append(c);
                }
            }
            if (backslashes > 0) sb.Append('\\', backslashes * 2);
            sb.Append('"');
            return sb.ToString();
        }

        public static string JoinArgs(IEnumerable<string> args)
        {
            return string.Join(" ", args.Select(Quote).ToArray());
        }

        public static string Sha256File(string path)
        {
            using (FileStream fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read, 1024 * 128))
            using (SHA256 sha = SHA256.Create())
            {
                byte[] hash = sha.ComputeHash(fs);
                return ToHex(hash);
            }
        }

        public static string Sha256Bytes(byte[] data)
        {
            using (SHA256 sha = SHA256.Create())
            {
                return ToHex(sha.ComputeHash(data));
            }
        }

        public static string ToHex(byte[] bytes)
        {
            StringBuilder sb = new StringBuilder(bytes.Length * 2);
            foreach (byte b in bytes) sb.Append(b.ToString("x2"));
            return sb.ToString();
        }

        public static void AtomicWriteAllText(string path, string text)
        {
            AtomicWriteAllBytes(path, new UTF8Encoding(false).GetBytes(text ?? string.Empty));
        }

        public static void AtomicWriteAllBytes(string path, byte[] data)
        {
            string dir = Path.GetDirectoryName(path);
            if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);
            string tmp = path + ".tmp-" + Guid.NewGuid().ToString("N");
            File.WriteAllBytes(tmp, data ?? new byte[0]);
            if (File.Exists(path))
            {
                try { File.Replace(tmp, path, null); return; }
                catch { }
                try { File.Delete(path); } catch { }
            }
            File.Move(tmp, path);
        }

        public static void TryDeleteDirectory(string path)
        {
            if (string.IsNullOrEmpty(path)) return;
            try { if (Directory.Exists(path)) Directory.Delete(path, true); } catch { }
        }

        public static void TryDeleteFile(string path)
        {
            try { if (File.Exists(path)) File.Delete(path); } catch { }
        }

        public static string SanitizeId(string value)
        {
            if (string.IsNullOrEmpty(value)) return "env";
            StringBuilder sb = new StringBuilder();
            foreach (char c in value)
            {
                if (char.IsLetterOrDigit(c) || c == '.' || c == '-' || c == '_') sb.Append(c);
                else sb.Append('-');
            }
            string result = sb.ToString().Trim('-', '.');
            if (result.Length == 0) result = "env";
            if (result.Length > 80) result = result.Substring(0, 80);
            return result;
        }

        public static string FormatBytes(long bytes)
        {
            if (bytes < 0) bytes = 0;
            string[] units = new string[] { "B", "KB", "MB", "GB", "TB" };
            double value = bytes;
            int unit = 0;
            while (value >= 1024 && unit < units.Length - 1)
            {
                value /= 1024;
                unit++;
            }
            return unit == 0 ? ((long)value).ToString() + " B" : value.ToString("0.0") + " " + units[unit];
        }

        public static string NowIso()
        {
            return DateTime.UtcNow.ToString("o");
        }

        public static bool FixedTimeEquals(string a, string b)
        {
            if (a == null) a = string.Empty;
            if (b == null) b = string.Empty;
            byte[] x = Encoding.UTF8.GetBytes(a);
            byte[] y = Encoding.UTF8.GetBytes(b);
            int diff = x.Length ^ y.Length;
            int len = Math.Min(x.Length, y.Length);
            for (int i = 0; i < len; i++) diff |= x[i] ^ y[i];
            return diff == 0;
        }

        public static string StripAnsi(string text)
        {
            if (string.IsNullOrEmpty(text)) return string.Empty;
            return System.Text.RegularExpressions.Regex.Replace(text, "\u001b\\[[0-9;]*m", string.Empty);
        }

        public static string[] ReadTail(string path, int maxLines)
        {
            try
            {
                if (!File.Exists(path)) return new string[0];
                string[] lines = File.ReadAllLines(path, Encoding.UTF8);
                if (lines.Length <= maxLines) return lines;
                string[] tail = new string[maxLines];
                Array.Copy(lines, lines.Length - maxLines, tail, 0, maxLines);
                return tail;
            }
            catch
            {
                return new string[0];
            }
        }

        public static long DirectorySize(string path)
        {
            if (string.IsNullOrEmpty(path) || !Directory.Exists(path)) return 0;
            long total = 0;
            Stack<string> stack = new Stack<string>();
            stack.Push(path);
            while (stack.Count > 0)
            {
                string dir = stack.Pop();
                try
                {
                    foreach (string file in Directory.GetFiles(dir))
                    {
                        try { total += new FileInfo(file).Length; } catch { }
                    }
                    foreach (string sub in Directory.GetDirectories(dir)) stack.Push(sub);
                }
                catch { }
            }
            return total;
        }

        public static long GetFreeBytes(string path)
        {
            try
            {
                string root = Path.GetPathRoot(Path.GetFullPath(path));
                DriveInfo drive = new DriveInfo(root);
                return drive.AvailableFreeSpace;
            }
            catch
            {
                return -1;
            }
        }

        public static void OpenUrl(string url)
        {
            ProcessStartInfo psi = new ProcessStartInfo(url);
            psi.UseShellExecute = true;
            Process.Start(psi);
        }

        public static void OpenFolder(string path)
        {
            if (!Directory.Exists(path)) Directory.CreateDirectory(path);
            ProcessStartInfo psi = new ProcessStartInfo("explorer.exe", Quote(path));
            psi.UseShellExecute = true;
            Process.Start(psi);
        }

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool AttachConsole(int processId);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool AllocConsole();

        public static void AttachConsole()
        {
            try { AttachConsole(-1); } catch { }
        }

        public static bool IsProcessAlive(int pid, DateTime startedAt)
        {
            if (pid <= 0) return false;
            try
            {
                Process p = Process.GetProcessById(pid);
                if (p.HasExited) return false;
                DateTime st = p.StartTime.ToUniversalTime();
                return Math.Abs((st - startedAt.ToUniversalTime()).TotalSeconds) < 5;
            }
            catch
            {
                return false;
            }
        }

        public static void KillTree(int pid)
        {
            if (pid <= 0) return;
            try
            {
                ProcessStartInfo psi = new ProcessStartInfo(Path.Combine(Environment.SystemDirectory, "taskkill.exe"),
                    "/T /F /PID " + pid.ToString());
                psi.UseShellExecute = false;
                psi.CreateNoWindow = true;
                psi.RedirectStandardOutput = true;
                psi.RedirectStandardError = true;
                using (Process p = Process.Start(psi))
                {
                    if (p != null) p.WaitForExit(5000);
                }
            }
            catch
            {
                try { Process.GetProcessById(pid).Kill(); } catch { }
            }
        }

        public static string ResolveRelative(string root, string relative)
        {
            if (string.IsNullOrEmpty(relative)) return root;
            if (Path.IsPathRooted(relative)) return relative;
            return Path.GetFullPath(Path.Combine(root, relative));
        }

        public static bool IsHttpUrl(string value)
        {
            Uri uri;
            return !string.IsNullOrEmpty(value) && Uri.TryCreate(value, UriKind.Absolute, out uri)
                && (uri.Scheme == Uri.UriSchemeHttps || uri.Scheme == Uri.UriSchemeHttp);
        }

        public static string Md5Hex(string text)
        {
            using (MD5 md5 = MD5.Create())
            {
                return ToHex(md5.ComputeHash(Encoding.UTF8.GetBytes(text ?? string.Empty)));
            }
        }

        public static string RandomHex(int bytes)
        {
            byte[] data = new byte[bytes];
            using (RandomNumberGenerator rng = RandomNumberGenerator.Create()) rng.GetBytes(data);
            return ToHex(data);
        }

        public static string FirstSemver(string text)
        {
            if (string.IsNullOrEmpty(text)) return "";
            System.Text.RegularExpressions.Match m =
                System.Text.RegularExpressions.Regex.Match(text, "(\\d+)\\.(\\d+)\\.(\\d+)");
            return m.Success ? m.Value : "";
        }

        public static bool VersionAtLeast(string actual, string required)
        {
            int[] a = ParseVersion(actual);
            int[] r = ParseVersion(required);
            if (a == null || r == null) return false;
            for (int i = 0; i < 3; i++)
            {
                if (a[i] > r[i]) return true;
                if (a[i] < r[i]) return false;
            }
            return true;
        }

        private static int[] ParseVersion(string text)
        {
            if (string.IsNullOrEmpty(text)) return null;
            System.Text.RegularExpressions.Match m =
                System.Text.RegularExpressions.Regex.Match(text, "(\\d+)\\.(\\d+)\\.(\\d+)");
            if (!m.Success) return null;
            int[] parts = new int[3];
            for (int i = 0; i < 3; i++) int.TryParse(m.Groups[i + 1].Value, out parts[i]);
            return parts;
        }
    }
}
