using System;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Text;

namespace SllkGui.Launcher
{
    internal static class Resources
    {
        private static Stream Open(string name)
        {
            Stream s = Assembly.GetExecutingAssembly().GetManifestResourceStream(name);
            if (s == null) throw new InvalidOperationException("缺少内嵌资源：" + name);
            return s;
        }

        public static byte[] ReadBytes(string name)
        {
            using (Stream s = Open(name))
            using (MemoryStream ms = new MemoryStream())
            {
                s.CopyTo(ms);
                return ms.ToArray();
            }
        }

        public static string ReadText(string name)
        {
            return Encoding.UTF8.GetString(ReadBytes(name));
        }

        public static string UiHtml()
        {
            try
            {
                using (Stream s = Open("Launcher.Ui.index.html.gz"))
                using (GZipStream gz = new GZipStream(s, CompressionMode.Decompress))
                using (MemoryStream ms = new MemoryStream())
                {
                    gz.CopyTo(ms);
                    return Encoding.UTF8.GetString(ms.ToArray());
                }
            }
            catch (InvalidOperationException)
            {
                return ReadText("Launcher.Ui.index.html");
            }
        }

        public static byte[] Icon()
        {
            return ReadBytes("Launcher.Ui.icon.ico");
        }

        public static string MihoutaoSvg()
        {
            return ReadText("Launcher.Ui.mihoutao.svg");
        }
    }
}
