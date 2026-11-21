using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.Web.Script.Serialization;

namespace SllkGui.Launcher
{
    internal static class Json
    {
        private static readonly JavaScriptSerializer Serializer = Create();

        private static JavaScriptSerializer Create()
        {
            JavaScriptSerializer s = new JavaScriptSerializer();
            s.MaxJsonLength = int.MaxValue;
            s.RecursionLimit = 100;
            return s;
        }

        public static string Stringify(object value)
        {
            return Serializer.Serialize(value);
        }

        public static Dictionary<string, object> ParseObject(string text)
        {
            if (string.IsNullOrEmpty(text) || text.Trim().Length == 0) return new Dictionary<string, object>();
            Dictionary<string, object> result = Serializer.Deserialize<Dictionary<string, object>>(text);
            return result ?? new Dictionary<string, object>();
        }

        public static object[] ParseArray(string text)
        {
            if (string.IsNullOrEmpty(text)) return new object[0];
            object[] result = Serializer.Deserialize<object[]>(text);
            return result ?? new object[0];
        }

        public static string Str(Dictionary<string, object> dict, string key, string fallback)
        {
            if (dict == null || !dict.ContainsKey(key) || dict[key] == null) return fallback;
            string value = Convert.ToString(dict[key], CultureInfo.InvariantCulture);
            return value == null ? fallback : value;
        }

        public static bool Bool(Dictionary<string, object> dict, string key, bool fallback)
        {
            if (dict == null || !dict.ContainsKey(key) || dict[key] == null) return fallback;
            object value = dict[key];
            if (value is bool) return (bool)value;
            bool parsed;
            if (bool.TryParse(Convert.ToString(value, CultureInfo.InvariantCulture), out parsed)) return parsed;
            long number;
            if (long.TryParse(Convert.ToString(value, CultureInfo.InvariantCulture), out number)) return number != 0;
            return fallback;
        }

        public static int Int(Dictionary<string, object> dict, string key, int fallback)
        {
            if (dict == null || !dict.ContainsKey(key) || dict[key] == null) return fallback;
            try { return Convert.ToInt32(dict[key], CultureInfo.InvariantCulture); }
            catch { return fallback; }
        }

        public static long Long(Dictionary<string, object> dict, string key, long fallback)
        {
            if (dict == null || !dict.ContainsKey(key) || dict[key] == null) return fallback;
            try { return Convert.ToInt64(dict[key], CultureInfo.InvariantCulture); }
            catch { return fallback; }
        }

        public static Dictionary<string, object> Dict(Dictionary<string, object> dict, string key)
        {
            if (dict == null || !dict.ContainsKey(key)) return new Dictionary<string, object>();
            Dictionary<string, object> value = dict[key] as Dictionary<string, object>;
            return value ?? new Dictionary<string, object>();
        }

        public static List<object> List(Dictionary<string, object> dict, string key)
        {
            List<object> result = new List<object>();
            if (dict == null || !dict.ContainsKey(key) || dict[key] == null) return result;
            object value = dict[key];
            object[] array = value as object[];
            if (array != null)
            {
                result.AddRange(array);
                return result;
            }
            IEnumerable enumerable = value as IEnumerable;
            if (enumerable != null && !(value is string) && !(value is Dictionary<string, object>))
            {
                foreach (object item in enumerable) result.Add(item);
            }
            return result;
        }
    }
}
