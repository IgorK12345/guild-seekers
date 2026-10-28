// PostgreSQL's Windows version probe uses COMSPEC. /d prevents the system's
// noisy cmd AutoRun from corrupting its output, without changing the registry.
using System;
using System.Diagnostics;
class QuietShell {
    static int Main() {
        string raw = Environment.CommandLine;
        int end = raw[0] == '"' ? raw.IndexOf('"', 1) + 1 : raw.IndexOf(' ');
        string arguments = end < 0 ? "" : raw.Substring(end).TrimStart();
        var info = new ProcessStartInfo(System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), "cmd.exe"), "/d " + arguments);
        info.UseShellExecute = false;
        info.CreateNoWindow = true;
        info.RedirectStandardOutput = true;
        info.RedirectStandardError = true;
        using (var child = Process.Start(info)) {
            child.OutputDataReceived += (s, e) => { if (e.Data != null) Console.Out.WriteLine(e.Data); };
            child.ErrorDataReceived += (s, e) => { if (e.Data != null) Console.Error.WriteLine(e.Data); };
            child.BeginOutputReadLine(); child.BeginErrorReadLine();
            child.WaitForExit(); return child.ExitCode;
        }
    }
}
