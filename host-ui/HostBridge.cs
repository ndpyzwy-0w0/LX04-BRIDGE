using System.Diagnostics;
using System.Text;
using System.Text.Json;

namespace LX04.HostUi;

internal sealed class HostBridge : IDisposable
{
    private readonly Process _proc;
    private readonly StreamWriter _stdin;
    private readonly CancellationTokenSource _cts = new();
    private readonly Dictionary<int, TaskCompletionSource<JsonElement>> _wait = new();
    private int _nextId = 1;
    public event Action<JsonElement>? Event;
    public bool Alive => !_proc.HasExited;

    public HostBridge()
    {
        var start = new ProcessStartInfo
        {
            RedirectStandardInput = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
            StandardOutputEncoding = Encoding.UTF8,
            StandardInputEncoding = Encoding.UTF8,
        };
        ResolveWorker(start);
        _proc = Process.Start(start) ?? throw new InvalidOperationException("无法启动上位机后端");
        _stdin = _proc.StandardInput;
        _ = Task.Run(ReadLoop);
    }

    private static void ResolveWorker(ProcessStartInfo start)
    {
        var baseDir = AppContext.BaseDirectory;
        foreach (var worker in new[]
                 {
                     Path.Combine(baseDir, "LX04-PC-Bridge-Worker.exe"),
                     Path.Combine(baseDir, "worker", "LX04-PC-Bridge-Worker.exe"),
                 })
        {
            if (File.Exists(worker))
            {
                start.FileName = worker;
                start.WorkingDirectory = Path.GetDirectoryName(worker) ?? baseDir;
                return;
            }
        }
        var here = new DirectoryInfo(baseDir);
        for (var i = 0; i < 8 && here != null; i++, here = here.Parent)
        {
            var py = Path.Combine(here.FullName, "host", "host_svc.py");
            if (File.Exists(py))
            {
                start.FileName = "python";
                start.ArgumentList.Add(py);
                start.WorkingDirectory = Path.Combine(here.FullName, "host");
                return;
            }
        }
        throw new FileNotFoundException("找不到 host_svc.py 或 LX04-PC-Bridge-Worker.exe");
    }

    private async Task ReadLoop()
    {
        try
        {
            while (await _proc.StandardOutput.ReadLineAsync() is { } line)
            {
                if (string.IsNullOrWhiteSpace(line))
                {
                    continue;
                }
                JsonElement el;
                try
                {
                    el = JsonDocument.Parse(line).RootElement.Clone();
                }
                catch
                {
                    continue;
                }
                if (el.TryGetProperty("id", out var idEl) && idEl.ValueKind == JsonValueKind.Number)
                {
                    var id = idEl.GetInt32();
                    lock (_wait)
                    {
                        if (_wait.Remove(id, out var tcs))
                        {
                            tcs.TrySetResult(el);
                        }
                    }
                    continue;
                }
                Event?.Invoke(el);
            }
        }
        catch
        {
            // process ended
        }
    }

    public async Task<JsonElement> Call(string method, object? paramsObj = null)
    {
        int id;
        var tcs = new TaskCompletionSource<JsonElement>(TaskCreationOptions.RunContinuationsAsynchronously);
        lock (_wait)
        {
            id = _nextId++;
            _wait[id] = tcs;
        }
        var payload = new Dictionary<string, object?>
        {
            ["id"] = id,
            ["method"] = method,
        };
        if (paramsObj != null)
        {
            payload["params"] = paramsObj;
        }
        var json = JsonSerializer.Serialize(payload, JsonOpts.Options);
        await _stdin.WriteLineAsync(json);
        await _stdin.FlushAsync();
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(60));
        await using (timeout.Token.Register(() => tcs.TrySetCanceled()))
        {
            return await tcs.Task;
        }
    }

    public Task Reply(string token, object? value) =>
        Call("answer", new { id = token, value });

    public async Task Shutdown()
    {
        try
        {
            await Call("shutdown");
        }
        catch
        {
        }
        try
        {
            if (!_proc.HasExited)
            {
                _proc.Kill(true);
            }
        }
        catch
        {
        }
    }

    public void Dispose()
    {
        _cts.Cancel();
        try
        {
            if (!_proc.HasExited)
            {
                _proc.Kill(true);
            }
        }
        catch
        {
        }
        _proc.Dispose();
    }
}
