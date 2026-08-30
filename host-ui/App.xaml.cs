using System.Runtime.InteropServices;
using Microsoft.UI.Xaml;

namespace LX04.HostUi;

public partial class App : Application
{
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int MessageBoxW(IntPtr hWnd, string text, string caption, uint type);

    private Window? _window;

    public App()
    {
        try
        {
            var tag = MainWindow.ReadShellTheme();
            if (tag == "dark")
            {
                RequestedTheme = ApplicationTheme.Dark;
            }
            else if (tag == "light")
            {
                RequestedTheme = ApplicationTheme.Light;
            }
        }
        catch
        {
        }
        InitializeComponent();
    }

    protected override void OnLaunched(LaunchActivatedEventArgs args)
    {
        try
        {
            _window = new MainWindow();
            _window.Activate();
        }
        catch (Exception ex)
        {
            var logDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "LX04-PC-Bridge");
            Directory.CreateDirectory(logDir);
            File.AppendAllText(Path.Combine(logDir, "boot.log"), ex + "\n");
            MessageBoxW(IntPtr.Zero, ex.ToString(), "LX04 PC Bridge", 0);
            throw;
        }
    }
}
