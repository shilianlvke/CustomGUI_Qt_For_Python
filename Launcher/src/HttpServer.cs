using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace SllkGui.Launcher
{
    internal sealed class HttpRequest
    {
        public string Method = "GET";
        public string Target = "/";
        public string Path = "/";
        public string Query = "";
        public string Body = "";
        public readonly Dictionary<string, string> Headers = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);

        public string Header(string name)
        {
            string value;
            return Headers.TryGetValue(name, out value) ? value : "";
        }
    }

    internal sealed class HttpResponse
    {
        public int Status = 200;
        public string ContentType = "text/plain; charset=utf-8";
        public byte[] Body = new byte[0];
        public readonly Dictionary<string, string> Headers = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);

        public static HttpResponse Json(object value)
        {
            HttpResponse r = new HttpResponse();
            r.ContentType = "application/json; charset=utf-8";
            r.Body = Encoding.UTF8.GetBytes(SllkGui.Launcher.Json.Stringify(value));
            return r;
        }

        public static HttpResponse Html(string html)
        {
            HttpResponse r = new HttpResponse();
            r.ContentType = "text/html; charset=utf-8";
            r.Body = Encoding.UTF8.GetBytes(html ?? "");
            return r;
        }

        public static HttpResponse Text(string text, int status)
        {
            HttpResponse r = new HttpResponse();
            r.Status = status;
            r.ContentType = "text/plain; charset=utf-8";
            r.Body = Encoding.UTF8.GetBytes(text ?? "");
            return r;
        }

        public static HttpResponse Bytes(byte[] data, string contentType)
        {
            HttpResponse r = new HttpResponse();
            r.ContentType = contentType;
            r.Body = data ?? new byte[0];
            return r;
        }

        public static HttpResponse Empty(int status)
        {
            HttpResponse r = new HttpResponse();
            r.Status = status;
            r.Body = new byte[0];
            return r;
        }
    }

    internal sealed class HttpServer
    {
        private readonly Func<HttpRequest, HttpResponse> _handler;
        private readonly LogBuffer _log;
        private TcpListener _listener;
        private CancellationTokenSource _cts;
        private Task _acceptTask;
        private const int MaxHeaderBytes = 64 * 1024;
        private const int MaxBodyBytes = 1024 * 1024;

        public int Port { get; private set; }

        public HttpServer(Func<HttpRequest, HttpResponse> handler, LogBuffer log)
        {
            _handler = handler;
            _log = log;
        }

        public void Start(int preferredPort)
        {
            _cts = new CancellationTokenSource();
            Exception last = null;
            for (int attempt = 0; attempt < 12; attempt++)
            {
                int port = preferredPort > 0 ? preferredPort + attempt : 0;
                try
                {
                    TcpListener listener = new TcpListener(IPAddress.Loopback, port);
                    listener.Start();
                    _listener = listener;
                    Port = ((IPEndPoint)listener.LocalEndpoint).Port;
                    break;
                }
                catch (Exception ex)
                {
                    last = ex;
                    if (preferredPort <= 0) break;
                }
            }
            if (_listener == null) throw new InvalidOperationException("无法绑定本地端口：" + (last == null ? "未知错误" : last.Message));
            CancellationToken ct = _cts.Token;
            _acceptTask = Task.Run(delegate { AcceptLoop(ct); });
            _log.Sys("本地界面已启动 · http://127.0.0.1:" + Port + "/");
        }

        public void Stop()
        {
            try { if (_cts != null) _cts.Cancel(); } catch { }
            try { if (_listener != null) _listener.Stop(); } catch { }
            try { if (_acceptTask != null) _acceptTask.Wait(1500); } catch { }
            try { if (_cts != null) _cts.Dispose(); } catch { }
            _listener = null;
        }

        private void AcceptLoop(CancellationToken ct)
        {
            while (!ct.IsCancellationRequested)
            {
                TcpClient client = null;
                try
                {
                    client = _listener.AcceptTcpClient();
                }
                catch
                {
                    if (ct.IsCancellationRequested) break;
                    Thread.Sleep(50);
                    continue;
                }
                TcpClient captured = client;
                Task.Run(delegate { HandleClient(captured); });
            }
        }

        private void HandleClient(TcpClient client)
        {
            using (client)
            {
                try
                {
                    client.NoDelay = true;
                    client.ReceiveTimeout = 15000;
                    client.SendTimeout = 15000;
                    NetworkStream stream = client.GetStream();
                    byte[] prefixBody;
                    string headerText = ReadHeaders(stream, out prefixBody);
                    if (headerText == null) return;
                    HttpRequest request;
                    HttpResponse response;
                    if (!TryParseRequest(headerText, out request, out response))
                    {
                        if (response != null) WriteResponse(stream, response, false);
                        return;
                    }
                    int length = 0;
                    string cl = request.Header("content-length");
                    if (!string.IsNullOrEmpty(cl) && !int.TryParse(cl, out length))
                    {
                        WriteResponse(stream, HttpResponse.Text("bad request", 400), false);
                        return;
                    }
                    if (length < 0 || length > MaxBodyBytes)
                    {
                        // 体量过大时尽量把已声明的内容读掉，避免客户端在写请求体时收到 RST；
                        // 超过 2 MB 则直接拒绝并关闭，防止被慢速大包拖住。
                        if (length > 0 && length <= 2 * 1024 * 1024)
                        {
                            byte[] discard = new byte[16384];
                            int left = length;
                            while (left > 0)
                            {
                                int read = stream.Read(discard, 0, Math.Min(left, discard.Length));
                                if (read <= 0) break;
                                left -= read;
                            }
                        }
                        WriteResponse(stream, HttpResponse.Text("payload too large", 413), false);
                        return;
                    }
                    if (length > 0)
                    {
                        byte[] body = new byte[length];
                        int offset = 0;
                        // 小请求的 header 与 body 常在同一个 TCP 包里；必须先消费读 header 时多读到的字节，
                        // 否则会误以为 body 还没到而阻塞到 ReceiveTimeout。
                        if (prefixBody != null && prefixBody.Length > 0)
                        {
                            int take = Math.Min(prefixBody.Length, length);
                            Array.Copy(prefixBody, 0, body, 0, take);
                            offset = take;
                        }
                        while (offset < length)
                        {
                            int read = stream.Read(body, offset, length - offset);
                            if (read <= 0) break;
                            offset += read;
                        }
                        request.Body = Encoding.UTF8.GetString(body, 0, offset);
                    }
                    string error = ValidateRequest(request);
                    if (!string.IsNullOrEmpty(error))
                    {
                        WriteResponse(stream, HttpResponse.Text(error, 403), false);
                        return;
                    }
                    try
                    {
                        response = _handler(request);
                    }
                    catch (Exception ex)
                    {
                        _log.Err("请求处理失败：" + ex.Message);
                        response = HttpResponse.Json(new Dictionary<string, object> { { "ok", false }, { "error", ex.Message } });
                        response.Status = 500;
                    }
                    WriteResponse(stream, response, string.Equals(request.Method, "HEAD", StringComparison.OrdinalIgnoreCase));
                }
                catch (Exception ex)
                {
                    try { _log.Sys("HTTP 连接结束：" + ex.Message); } catch { }
                }
            }
        }

        private string ValidateRequest(HttpRequest request)
        {
            string host = request.Header("host");
            if (string.IsNullOrEmpty(host)) return "forbidden";
            string hostOnly = host;
            int colon = host.LastIndexOf(':');
            if (colon > 0 && host[0] != '[')
            {
                int port;
                if (int.TryParse(host.Substring(colon + 1), out port) && port != Port) return "forbidden";
                hostOnly = host.Substring(0, colon);
            }
            hostOnly = hostOnly.Trim().ToLowerInvariant();
            if (hostOnly != "127.0.0.1" && hostOnly != "localhost") return "forbidden";
            string origin = request.Header("origin");
            if (!string.IsNullOrEmpty(origin))
            {
                string expected1 = "http://127.0.0.1:" + Port;
                string expected2 = "http://localhost:" + Port;
                if (!string.Equals(origin, expected1, StringComparison.OrdinalIgnoreCase) &&
                    !string.Equals(origin, expected2, StringComparison.OrdinalIgnoreCase))
                    return "forbidden";
            }
            return "";
        }

        private bool TryParseRequest(string headerText, out HttpRequest request, out HttpResponse error)
        {
            request = new HttpRequest();
            error = null;
            string[] lines = headerText.Split(new string[] { "\r\n" }, StringSplitOptions.None);
            if (lines.Length == 0) return false;
            string[] first = lines[0].Split(' ');
            if (first.Length < 3) return false;
            request.Method = first[0].ToUpperInvariant();
            string target = first[1];
            int q = target.IndexOf('?');
            if (q >= 0)
            {
                request.Query = target.Substring(q + 1);
                request.Path = target.Substring(0, q);
            }
            else
            {
                request.Path = target;
            }
            try { request.Path = Uri.UnescapeDataString(request.Path); } catch { }
            for (int i = 1; i < lines.Length; i++)
            {
                string line = lines[i];
                if (line.Length == 0) break;
                int idx = line.IndexOf(':');
                if (idx <= 0) continue;
                request.Headers[line.Substring(0, idx).Trim()] = line.Substring(idx + 1).Trim();
            }
            if (request.Method != "GET" && request.Method != "POST" && request.Method != "HEAD" && request.Method != "OPTIONS")
            {
                error = HttpResponse.Text("method not allowed", 405);
                return false;
            }
            return true;
        }

        private string ReadHeaders(NetworkStream stream, out byte[] prefixBody)
        {
            prefixBody = new byte[0];
            MemoryStream ms = new MemoryStream();
            byte[] buffer = new byte[4096];
            while (ms.Length <= MaxHeaderBytes)
            {
                int read = stream.Read(buffer, 0, buffer.Length);
                if (read <= 0) return null;
                ms.Write(buffer, 0, read);
                byte[] data = ms.ToArray();
                for (int i = 0; i <= data.Length - 4; i++)
                {
                    if (data[i] == 13 && data[i + 1] == 10 && data[i + 2] == 13 && data[i + 3] == 10)
                    {
                        int bodyStart = i + 4;
                        int bodyLength = data.Length - bodyStart;
                        if (bodyLength > 0)
                        {
                            prefixBody = new byte[bodyLength];
                            Array.Copy(data, bodyStart, prefixBody, 0, bodyLength);
                        }
                        return Encoding.UTF8.GetString(data, 0, i);
                    }
                }
            }
            return null;
        }

        private static readonly Dictionary<int, string> Reasons = new Dictionary<int, string>
        {
            {200, "OK"}, {204, "No Content"}, {400, "Bad Request"}, {403, "Forbidden"},
            {404, "Not Found"}, {405, "Method Not Allowed"}, {413, "Payload Too Large"}, {500, "Internal Server Error"}
        };

        private void WriteResponse(NetworkStream stream, HttpResponse response, bool headOnly)
        {
            if (response == null) response = HttpResponse.Empty(500);
            string reason;
            if (!Reasons.TryGetValue(response.Status, out reason)) reason = "OK";
            StringBuilder head = new StringBuilder();
            head.Append("HTTP/1.1 ").Append(response.Status).Append(' ').Append(reason).Append("\r\n");
            head.Append("Content-Type: ").Append(response.ContentType).Append("\r\n");
            head.Append("Content-Length: ").Append(response.Body.Length).Append("\r\n");
            head.Append("Cache-Control: no-store\r\n");
            head.Append("Connection: close\r\n");
            head.Append("X-Content-Type-Options: nosniff\r\n");
            head.Append("X-Frame-Options: DENY\r\n");
            head.Append("Referrer-Policy: no-referrer\r\n");
            head.Append("Permissions-Policy: geolocation=(), camera=(), microphone=()\r\n");
            foreach (KeyValuePair<string, string> kv in response.Headers) head.Append(kv.Key).Append(": ").Append(kv.Value).Append("\r\n");
            head.Append("\r\n");
            byte[] bytes = Encoding.UTF8.GetBytes(head.ToString());
            stream.Write(bytes, 0, bytes.Length);
            if (!headOnly && response.Body.Length > 0) stream.Write(response.Body, 0, response.Body.Length);
            stream.Flush();
        }
    }
}
