using System.Runtime.InteropServices;
using Microsoft.UI.Dispatching;
using Microsoft.UI.Xaml;

namespace LX04.HostUi;

internal static class Program
{
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int MessageBoxW(IntPtr hWnd, string text, string caption, uint type);

    [STAThread]
    private static void Main(string[] args)
    {
        try
        {
            var logDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "LX04-PC-Bridge");
            Directory.CreateDirectory(logDir);
            File.AppendAllText(Path.Combine(logDir, "boot.log"), DateTime.Now.ToString("o") + " main\n");
            if (!SingleInstance.Claim())
            {
                SingleInstance.SignalRunning();
                return;
            }
            WinRT.ComWrappersSupport.InitializeComWrappers();
            Application.Start(p =>
            {
                var context = new DispatcherQueueSynchronizationContext(DispatcherQueue.GetForCurrentThread());
                SynchronizationContext.SetSynchronizationContext(context);
                new App();
            });
        }
        catch (Exception ex)
        {
            try
            {
                var logDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "LX04-PC-Bridge");
                Directory.CreateDirectory(logDir);
                File.AppendAllText(Path.Combine(logDir, "boot.log"), ex + "\n");
            }
            catch
            {
            }
            MessageBoxW(IntPtr.Zero, ex.ToString(), "LX04 PC Bridge", 0);
        }
    }
}
