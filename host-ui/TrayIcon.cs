using System.Runtime.InteropServices;

namespace LX04.HostUi;

internal sealed class TrayIcon : IDisposable
{
    private const int WmTray = 0x8001;
    private const int NimAdd = 0;
    private const int NimDelete = 2;
    private const int NifMessage = 1;
    private const int NifIcon = 2;
    private const int NifTip = 4;
    private const int WmLButtonUp = 0x0202;
    private const int WmRButtonUp = 0x0205;
    private const int IdiApplication = 32512;

    private IntPtr _hwnd;
    private bool _added;
    public event Action? Open;
    public event Action? Quit;

    private delegate IntPtr WndProc(IntPtr hWnd, uint msg, IntPtr w, IntPtr l);
    private WndProc? _proc;

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern ushort RegisterClassW(ref WndClass wc);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern IntPtr CreateWindowExW(int ex, string cls, string name, int style, int x, int y, int w, int h, IntPtr parent, IntPtr menu, IntPtr inst, IntPtr param);

    [DllImport("user32.dll")]
    private static extern IntPtr DefWindowProcW(IntPtr h, uint m, IntPtr w, IntPtr l);

    [DllImport("user32.dll")]
    private static extern bool DestroyWindow(IntPtr h);

    [DllImport("user32.dll")]
    private static extern IntPtr LoadIconW(IntPtr inst, IntPtr name);

    [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
    private static extern bool Shell_NotifyIconW(int msg, ref NotifyData data);

    [DllImport("kernel32.dll")]
    private static extern IntPtr GetModuleHandleW(string? name);

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct WndClass
    {
        public uint style;
        public WndProc lpfnWndProc;
        public int cbClsExtra;
        public int cbWndExtra;
        public IntPtr hInstance;
        public IntPtr hIcon;
        public IntPtr hCursor;
        public IntPtr hbrBackground;
        public string? lpszMenuName;
        public string lpszClassName;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct NotifyData
    {
        public int cbSize;
        public IntPtr hWnd;
        public uint uID;
        public uint uFlags;
        public uint uCallbackMessage;
        public IntPtr hIcon;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 128)]
        public string szTip;
    }

    public void Show()
    {
        if (_added)
        {
            return;
        }
        _proc = Wnd;
        var wc = new WndClass
        {
            lpfnWndProc = _proc,
            hInstance = GetModuleHandleW(null),
            lpszClassName = "LX04BridgeTrayUi",
        };
        RegisterClassW(ref wc);
        _hwnd = CreateWindowExW(0x00000080, "LX04BridgeTrayUi", "LX04 Tray", unchecked((int)0x80000000), -32000, -32000, 1, 1, IntPtr.Zero, IntPtr.Zero, wc.hInstance, IntPtr.Zero);
        var nid = Nid();
        _added = Shell_NotifyIconW(NimAdd, ref nid);
    }

    public void Hide()
    {
        if (!_added)
        {
            return;
        }
        var nid = Nid();
        Shell_NotifyIconW(NimDelete, ref nid);
        _added = false;
        if (_hwnd != IntPtr.Zero)
        {
            DestroyWindow(_hwnd);
            _hwnd = IntPtr.Zero;
        }
    }

    private NotifyData Nid() => new()
    {
        cbSize = Marshal.SizeOf<NotifyData>(),
        hWnd = _hwnd,
        uID = 1,
        uFlags = NifMessage | NifIcon | NifTip,
        uCallbackMessage = WmTray,
        hIcon = LoadIconW(IntPtr.Zero, (IntPtr)IdiApplication),
        szTip = "LX04 PC Bridge",
    };

    private IntPtr Wnd(IntPtr h, uint msg, IntPtr w, IntPtr l)
    {
        if (msg == WmTray)
        {
            var ev = l.ToInt32() & 0xFFFF;
            if (ev == WmLButtonUp)
            {
                Open?.Invoke();
            }
            if (ev == WmRButtonUp)
            {
                Quit?.Invoke();
            }
        }
        return DefWindowProcW(h, msg, w, l);
    }

    public void Dispose() => Hide();
}
