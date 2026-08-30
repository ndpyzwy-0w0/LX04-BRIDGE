using System.Runtime.InteropServices;
using Microsoft.UI.Dispatching;
using Microsoft.UI.Xaml;

namespace LX04.HostUi;

internal static class Program
{
    [STAThread]
    private static void Main(string[] args)
    {
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
}
