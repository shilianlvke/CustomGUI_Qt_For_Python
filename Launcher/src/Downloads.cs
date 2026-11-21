using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Net;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;

namespace SllkGui.Launcher
{
    internal sealed class DownloadProgress
    {
        public bool Active;
        public string Label = "";
        public long Received;
        public long Total;
        public int Percent;
        public string Text = "";

        public Dictionary<string, object> ToDto()
        {
            Dictionary<string, object> d = new Dictionary<string, object>();
            d["active"] = Active;
            d["label"] = Label;
            d["received"] = Received;
            d["total"] = Total;
            d["percent"] = Percent;
            d["text"] = Text;
            return d;
        }
    }

    internal sealed class Downloader
    {
        private readonly LauncherPaths _paths;
        private readonly LogBuffer _log;
        private readonly HttpClient _http;
        private readonly Action<DownloadProgress> _progress;

        public Downloader(LauncherPaths paths, LogBuffer log, Action<DownloadProgress> progress)
        {
            _paths = paths;
            _log = log;
            _progress = progress;
            ServicePointManager.SecurityProtocol |= SecurityProtocolType.Tls12;
            HttpClientHandler handler = new HttpClientHandler();
            handler.AllowAutoRedirect = true;
            handler.AutomaticDecompression = DecompressionMethods.GZip | DecompressionMethods.Deflate;
            _http = new HttpClient(handler);
            _http.Timeout = TimeSpan.FromMinutes(30);
            _http.DefaultRequestHeaders.UserAgent.ParseAdd("SllkGuiLauncher/5.0");
        }

        private void Report(DownloadProgress p)
        {
            if (_progress != null) { try { _progress(p); } catch { } }
        }

        public async Task<string> DownloadAsync(string url, string dest, string expectedSha256, string label, long expectedBytes, CancellationToken ct)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(dest));
            if (File.Exists(dest) && !string.IsNullOrEmpty(expectedSha256))
            {
                string existing = Util.Sha256File(dest);
                if (string.Equals(existing, expectedSha256, StringComparison.OrdinalIgnoreCase))
                {
                    _log.Ok(label + " 已存在且校验通过");
                    Report(new DownloadProgress { Active = false, Label = label, Received = new FileInfo(dest).Length, Total = new FileInfo(dest).Length, Percent = 100, Text = "已存在" });
                    return dest;
                }
                _log.Warn(label + " 已存在但哈希不符，重新下载");
                Util.TryDeleteFile(dest);
            }

            Exception last = null;
            for (int attempt = 1; attempt <= 3; attempt++)
            {
                ct.ThrowIfCancellationRequested();
                try
                {
                    await DownloadOnce(url, dest, label, expectedBytes, ct);
                    if (expectedBytes > 0 && new FileInfo(dest).Length != expectedBytes)
                    {
                        Util.TryDeleteFile(dest);
                        throw new InvalidOperationException(label + " 大小不符：期望 " + expectedBytes + " B，实际 " + new FileInfo(dest).Length + " B");
                    }
                    string actual = Util.Sha256File(dest);
                    if (!string.IsNullOrEmpty(expectedSha256) && !string.Equals(actual, expectedSha256, StringComparison.OrdinalIgnoreCase))
                    {
                        Util.TryDeleteFile(dest);
                        throw new InvalidOperationException(label + " 校验失败：期望 " + expectedSha256.Substring(0, 12) + "…，实际 " + actual.Substring(0, 12) + "…");
                    }
                    _log.Ok(label + " 下载完成 · " + Util.FormatBytes(new FileInfo(dest).Length));
                    Report(new DownloadProgress { Active = false, Label = label, Received = new FileInfo(dest).Length, Total = new FileInfo(dest).Length, Percent = 100, Text = "完成" });
                    return dest;
                }
                catch (OperationCanceledException) { throw; }
                catch (Exception ex)
                {
                    last = ex;
                    _log.Warn(label + " 下载失败（" + attempt + "/3）：" + ex.Message);
                    if (attempt < 3) System.Threading.Thread.Sleep(2000);
                }
            }
            throw new InvalidOperationException(label + " 下载失败：" + (last == null ? "未知错误" : last.Message), last);
        }

        private async Task DownloadOnce(string url, string dest, string label, long expectedBytes, CancellationToken ct)
        {
            string part = dest + ".part";
            long existing = 0;
            try { if (File.Exists(part)) existing = new FileInfo(part).Length; } catch { existing = 0; }

            HttpRequestMessage req = new HttpRequestMessage(HttpMethod.Get, url);
            if (existing > 0) req.Headers.Range = new System.Net.Http.Headers.RangeHeaderValue(existing, null);
            _log.Net("下载 " + label + " · " + url);

            using (HttpResponseMessage resp = await _http.SendAsync(req, HttpCompletionOption.ResponseHeadersRead, ct))
            {
                if (resp.StatusCode == HttpStatusCode.RequestedRangeNotSatisfiable)
                {
                    Util.TryDeleteFile(part);
                    throw new InvalidOperationException("续传范围失效，将重新下载");
                }
                if (!resp.IsSuccessStatusCode)
                    throw new InvalidOperationException("HTTP " + (int)resp.StatusCode + " " + resp.ReasonPhrase);

                bool append = resp.StatusCode == HttpStatusCode.PartialContent && existing > 0;
                long total = resp.Content.Headers.ContentLength.HasValue ? resp.Content.Headers.ContentLength.Value : 0;
                if (append) total += existing;
                if (total <= 0 && expectedBytes > 0) total = expectedBytes;

                using (Stream input = await resp.Content.ReadAsStreamAsync())
                using (FileStream output = new FileStream(part, append ? FileMode.Append : FileMode.Create, FileAccess.Write, FileShare.None, 1024 * 128, true))
                {
                    byte[] buffer = new byte[1024 * 128];
                    long received = append ? existing : 0;
                    DateTime lastReport = DateTime.MinValue;
                    long lastLogged = 0;
                    while (true)
                    {
                        ct.ThrowIfCancellationRequested();
                        int read = await input.ReadAsync(buffer, 0, buffer.Length, ct);
                        if (read <= 0) break;
                        await output.WriteAsync(buffer, 0, read, ct);
                        received += read;
                        DateTime now = DateTime.Now;
                        if ((now - lastReport).TotalMilliseconds > 250 || (total > 0 && received >= total))
                        {
                            int percent = total > 0 ? (int)Math.Min(100, received * 100 / total) : 0;
                            Report(new DownloadProgress
                            {
                                Active = true,
                                Label = label,
                                Received = received,
                                Total = total,
                                Percent = percent,
                                Text = Util.FormatBytes(received) + (total > 0 ? " / " + Util.FormatBytes(total) : "")
                            });
                            lastReport = now;
                        }
                        if (received - lastLogged > 4 * 1024 * 1024)
                        {
                            _log.Net(label + " " + Util.FormatBytes(received) + (total > 0 ? " / " + Util.FormatBytes(total) : ""));
                            lastLogged = received;
                        }
                    }
                    output.Flush();
                }
                if (File.Exists(dest)) Util.TryDeleteFile(dest);
                File.Move(part, dest);
            }
        }

        public void ExtractZip(string zip, string dest)
        {
            Util.TryDeleteDirectory(dest);
            Directory.CreateDirectory(dest);
            ZipFile.ExtractToDirectory(zip, dest);
        }

        public void Dispose()
        {
            try { _http.Dispose(); } catch { }
        }
    }
}
