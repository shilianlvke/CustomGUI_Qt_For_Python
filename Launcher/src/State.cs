using System;
using System.Collections.Generic;

namespace SllkGui.Launcher
{
    internal sealed class StepState
    {
        public string State = "wait";
        public string Note = "";
    }

    internal sealed class LauncherState
    {
        public readonly object Lock = new object();
        public string Phase = "idle";
        public string Error = "";
        public string Current = "";
        public DateTime? StartedAt;
        public DateTime? FinishedAt;
        public bool Cancel;
        public string UpdateRef = "";
        public Dictionary<string, object> SyncSummary;
        public readonly Dictionary<string, StepState> Steps = new Dictionary<string, StepState>(StringComparer.OrdinalIgnoreCase);
        public readonly DownloadProgress Download = new DownloadProgress();

        public void Reset(string phase)
        {
            lock (Lock)
            {
                Phase = phase;
                Error = "";
                Current = "";
                StartedAt = DateTime.Now;
                FinishedAt = null;
                Cancel = false;
                UpdateRef = "";
                SyncSummary = null;
                Steps.Clear();
                Download.Active = false;
                Download.Label = "";
                Download.Received = 0;
                Download.Total = 0;
                Download.Percent = 0;
                Download.Text = "";
            }
        }

        public void SetStep(string id, string state, string note)
        {
            lock (Lock)
            {
                Steps[id] = new StepState { State = state, Note = note ?? "" };
                if (state == "active") Current = id;
                if (state == "ok" || state == "fail") Current = "";
            }
        }
    }
}
