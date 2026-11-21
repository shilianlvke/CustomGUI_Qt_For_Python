using System;
using System.Collections.Generic;
using System.IO;
using System.Text;

namespace SllkGui.Launcher
{
    internal sealed class LogLine
    {
        public string t;
        public string level;
        public string text;

        public LogLine(string time, string level, string text)
        {
            this.t = time;
            this.level = level;
            this.text = text;
        }

        public Dictionary<string, object> ToDto()
        {
            Dictionary<string, object> d = new Dictionary<string, object>();
            d["t"] = t;
            d["level"] = level;
            d["text"] = text;
            return d;
        }
    }

    internal sealed class LogBuffer
    {
        private readonly object _lock = new object();
        private readonly List<LogLine> _lines = new List<LogLine>();
        private readonly string _path;
        private int _dropped;
        private StreamWriter _writer;
        private long _written;
        private const long MaxBytes = 2 * 1024 * 1024;
        private const int MaxLines = 5000;

        public LogBuffer(string path)
        {
            _path = path;
        }

        public void Sys(string text) { Write("sys", text); }
        public void Cmd(string text) { Write("cmd", text); }
        public void Out(string text) { Write("out", text); }
        public void Net(string text) { Write("net", text); }
        public void Ok(string text) { Write("ok", text); }
        public void Warn(string text) { Write("warn", text); }
        public void Err(string text) { Write("err", text); }

        public void Write(string level, string text)
        {
            if (text == null) text = string.Empty;
            string clock = DateTime.Now.ToString("HH:mm:ss");
            LogLine line = new LogLine(clock, level, text);
            lock (_lock)
            {
                _lines.Add(line);
                if (_lines.Count > MaxLines)
                {
                    int drop = _lines.Count - (MaxLines - 1000);
                    _lines.RemoveRange(0, drop);
                    _dropped += drop;
                }
                try
                {
                    EnsureWriter();
                    _writer.WriteLine(DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + " [" + level + "] " + text);
                    _writer.Flush();
                    _written += text.Length + 32;
                    if (_written > MaxBytes) Rotate();
                }
                catch
                {
                    try { _writer = null; } catch { }
                }
            }
        }

        private void EnsureWriter()
        {
            if (_writer != null) return;
            string dir = Path.GetDirectoryName(_path);
            if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);
            FileStream fs = new FileStream(_path, FileMode.Append, FileAccess.Write, FileShare.ReadWrite);
            _writer = new StreamWriter(fs, new UTF8Encoding(false));
            _writer.AutoFlush = true;
            _written = fs.Length;
        }

        private void Rotate()
        {
            try
            {
                if (_writer != null) { _writer.Dispose(); _writer = null; }
                string old = _path + ".1";
                if (File.Exists(old)) File.Delete(old);
                if (File.Exists(_path)) File.Move(_path, old);
                _written = 0;
            }
            catch { }
        }

        public Dictionary<string, object> Snapshot(int cursor)
        {
            Dictionary<string, object> result = new Dictionary<string, object>();
            lock (_lock)
            {
                int total = _dropped + _lines.Count;
                if (cursor < 0) cursor = 0;
                if (cursor > total) cursor = total;
                int from = cursor - _dropped;
                if (from < 0) from = 0;
                if (from > _lines.Count) from = _lines.Count;
                List<object> lines = new List<object>();
                for (int i = from; i < _lines.Count; i++) lines.Add(_lines[i].ToDto());
                result["cursor"] = total;
                result["lines"] = lines;
            }
            return result;
        }

        public List<LogLine> Recent(int max)
        {
            List<LogLine> result = new List<LogLine>();
            lock (_lock)
            {
                int start = Math.Max(0, _lines.Count - max);
                for (int i = start; i < _lines.Count; i++) result.Add(_lines[i]);
            }
            return result;
        }
    }
}
