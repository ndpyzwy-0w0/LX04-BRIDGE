using System.Runtime.InteropServices;

namespace LX04.HostUi;

internal static class SingleInstance
{
    private const string MutexName = @"Local\LX04PCBridgeHost";
    private const string EventName = @"Local\LX04PCBridgeActivate";
    private static Mutex? _mutex;

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr CreateEventW(IntPtr attr, bool manual, bool initial, string name);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool SetEvent(IntPtr handle);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool ResetEvent(IntPtr handle);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern uint WaitForSingleObject(IntPtr handle, uint ms);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool CloseHandle(IntPtr handle);

    private static IntPtr _event;

    public static bool Claim()
    {
        _mutex = new Mutex(true, MutexName, out var created);
        _event = CreateEventW(IntPtr.Zero, true, false, EventName);
        if (created)
        {
            return true;
        }
        SignalRunning();
        _mutex.Dispose();
        _mutex = null;
        if (_event != IntPtr.Zero)
        {
            CloseHandle(_event);
            _event = IntPtr.Zero;
        }
        return false;
    }

    public static void SignalRunning()
    {
        var ev = _event != IntPtr.Zero ? _event : CreateEventW(IntPtr.Zero, true, false, EventName);
        if (ev != IntPtr.Zero)
        {
            SetEvent(ev);
            if (_event == IntPtr.Zero)
            {
                CloseHandle(ev);
            }
        }
    }

    public static bool PollActivate()
    {
        if (_event == IntPtr.Zero)
        {
            return false;
        }
        if (WaitForSingleObject(_event, 0) == 0)
        {
            ResetEvent(_event);
            return true;
        }
        return false;
    }
}
