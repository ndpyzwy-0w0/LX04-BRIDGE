using System.Text;
using System.Text.Json;
using Microsoft.UI;
using Microsoft.UI.Windowing;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;
using Windows.Graphics;
using Windows.Storage.Pickers;
using Windows.UI;
using WinRT.Interop;

namespace LX04.HostUi;

public sealed partial class MainWindow : Window
{
    private readonly HostBridge _bridge;
    private readonly DispatcherTimer _activateTimer = new() { Interval = TimeSpan.FromMilliseconds(400) };
    private readonly TrayIcon _tray = new();
    private readonly List<(string Level, string Line)> _logs = new();
    private Snapshot _snap = new();
    private bool _applying;
    private bool _closing;
    private string _logFilter = "全部";
    private string _lastLog = "";

    public MainWindow()
    {
        InitializeComponent();
        Title = "LX04 PC Bridge";
        try
        {
            SystemBackdrop = new MicaBackdrop();
        }
        catch
        {
        }
        BuildUi();
        TryResize(800, 600);
        ApplySavedTheme();
        _bridge = new HostBridge();
        _bridge.Event += OnBridgeEvent;
        _activateTimer.Tick += (_, _) =>
        {
            if (SingleInstance.PollActivate())
            {
                Restore();
            }
        };
        _activateTimer.Start();
        _tray.Open += () => DispatcherQueue.TryEnqueue(Restore);
        _tray.Quit += () => DispatcherQueue.TryEnqueue(() => _ = CloseForReal());
        Closed += MainWindow_Closed;
    }

    private void TryResize(int w, int h)
    {
        try
        {
            var hwnd = WindowNative.GetWindowHandle(this);
            var id = Win32Interop.GetWindowIdFromWindow(hwnd);
            var app = AppWindow.GetFromWindowId(id);
            app.Resize(new SizeInt32(w, h));
        }
        catch
        {
        }
    }

    private async void MainWindow_Closed(object sender, WindowEventArgs args)
    {
        if (_closing)
        {
            return;
        }
        if (_snap.MinimizeToTray)
        {
            args.Handled = true;
            AppWindow.Hide();
            _tray.Show();
            return;
        }
        args.Handled = true;
        await CloseForReal();
    }

    private async Task CloseForReal()
    {
        if (_closing)
        {
            return;
        }
        _closing = true;
        _tray.Hide();
        await _bridge.Shutdown();
        _bridge.Dispose();
        Close();
    }

    private void Restore()
    {
        _tray.Hide();
        AppWindow.Show();
        Activate();
    }

    private void Nav_SelectionChanged(NavigationView sender, NavigationViewSelectionChangedEventArgs args)
    {
        var tag = (args.SelectedItem as NavigationViewItem)?.Tag as string ?? "overview";
        OverviewPage.Visibility = tag == "overview" ? Visibility.Visible : Visibility.Collapsed;
        AudioPage.Visibility = tag == "audio" ? Visibility.Visible : Visibility.Collapsed;
        ScreenPage.Visibility = tag == "screen" ? Visibility.Visible : Visibility.Collapsed;
        SettingsPage.Visibility = tag == "settings" ? Visibility.Visible : Visibility.Collapsed;
        LogPage.Visibility = tag == "log" ? Visibility.Visible : Visibility.Collapsed;
        PageTitle.Text = tag switch
        {
            "audio" => "音频",
            "screen" => "屏幕",
            "settings" => "设置",
            "log" => "日志",
            _ => "总览",
        };
        PageSub.Text = tag switch
        {
            "audio" => "LX04 麦克风与 Windows 扬声器",
            "screen" => "800×480 监视、镜像与弹窗",
            "settings" => "外观与系统",
            "log" => "调试信息",
            _ => "连接状态与诊断",
        };
    }

    private void OnBridgeEvent(JsonElement el)
    {
        DispatcherQueue.TryEnqueue(() => _ = HandleEvent(el));
    }

    private async Task HandleEvent(JsonElement el)
    {
        var kind = el.TryGetProperty("event", out var ev) ? ev.GetString() : "";
        if (kind == "ready" || kind == "snapshot")
        {
            if (el.TryGetProperty("data", out var data))
            {
                ApplySnapshot(ParseSnap(data));
            }
            return;
        }
        if (kind == "meter")
        {
            if (el.TryGetProperty("mic", out var mic))
            {
                MicMeter.Value = Clamp01(mic.GetDouble());
            }
            if (el.TryGetProperty("spk", out var spk))
            {
                SpkMeter.Value = Clamp01(spk.GetDouble());
            }
            return;
        }
        if (kind == "log")
        {
            var line = el.TryGetProperty("line", out var l) ? l.GetString() ?? "" : "";
            var level = el.TryGetProperty("level", out var lv) ? lv.GetString() ?? "INFO" : "INFO";
            AddLog(level, line);
            return;
        }
        if (kind == "alert")
        {
            var text = el.TryGetProperty("text", out var t) ? t.GetString() ?? "" : "";
            var dlg = new ContentDialog
            {
                Title = "LX04",
                Content = text,
                CloseButtonText = "确定",
                XamlRoot = Content.XamlRoot,
            };
            await dlg.ShowAsync();
            return;
        }
        if (kind == "confirm")
        {
            var id = el.GetProperty("id").GetString() ?? "";
            var text = el.TryGetProperty("text", out var t) ? t.GetString() ?? "" : "";
            var dlg = new ContentDialog
            {
                Title = "LX04",
                Content = text,
                PrimaryButtonText = "确定",
                CloseButtonText = "取消",
                XamlRoot = Content.XamlRoot,
            };
            var result = await dlg.ShowAsync();
            await _bridge.Reply(id, result == ContentDialogResult.Primary);
            return;
        }
        if (kind == "pick_file")
        {
            var id = el.GetProperty("id").GetString() ?? "";
            var picker = new FileOpenPicker();
            InitializeWithWindow.Initialize(picker, WindowNative.GetWindowHandle(this));
            picker.FileTypeFilter.Add(".jpg");
            picker.FileTypeFilter.Add(".jpeg");
            picker.FileTypeFilter.Add(".png");
            picker.FileTypeFilter.Add(".bmp");
            picker.FileTypeFilter.Add(".webp");
            var file = await picker.PickSingleFileAsync();
            await _bridge.Reply(id, file?.Path);
            return;
        }
        if (kind == "pick_slot")
        {
            var id = el.GetProperty("id").GetString() ?? "";
            var dlg = new ContentDialog
            {
                Title = "背景库已满",
                Content = "请选择要替换的一张",
                PrimaryButtonText = "替换 1",
                SecondaryButtonText = "替换 2",
                CloseButtonText = "取消",
                XamlRoot = Content.XamlRoot,
            };
            var result = await dlg.ShowAsync();
            object? slot = result switch
            {
                ContentDialogResult.Primary => 0,
                ContentDialogResult.Secondary => 1,
                _ => null,
            };
            await _bridge.Reply(id, slot);
        }
    }

    private static Snapshot ParseSnap(JsonElement data) =>
        data.Deserialize<Snapshot>(JsonOpts.Options) ?? new Snapshot();

    private void ApplySnapshot(Snapshot snap)
    {
        _applying = true;
        _snap = snap;
        try
        {
            var connected = snap.Connected;
            ConnectBar.Severity = snap.Connecting ? InfoBarSeverity.Informational : connected ? InfoBarSeverity.Success : InfoBarSeverity.Warning;
            ConnectBar.Title = snap.Headline;
            ConnectBar.Message = connected
                ? $"{snap.Model} · USB / ADB" + (snap.Elapsed > 0 ? $"\n连接时间：{TimeSpan.FromSeconds(snap.Elapsed):hh\\:mm\\:ss}" : "")
                : snap.Detail;
            DeviceLine.Text = snap.Devices.Count > 0 ? (snap.Device.Length > 0 ? snap.Device : snap.Devices[0]) : "未检测到 LX04";
            DeviceSub.Text = connected ? "ADB 已连接 · USB 数据通道正常" : snap.Devices.Count > 0 ? "ADB · USB" : "插入数据线后点刷新";
            ConnectBtn.Visibility = connected ? Visibility.Collapsed : Visibility.Visible;
            DisconnectBtn.Visibility = connected ? Visibility.Visible : Visibility.Collapsed;
            FillBox(InjectBox, snap.InjectLabels, snap.Inject);
            FillBox(SpeakerBox, snap.SpeakerLabels, snap.Speaker);
            FillBox(MonitorBox, snap.MonitorLabels, snap.Monitor);
            FillBox(QualityBox, snap.QualityLabels, snap.Quality);
            FillBox(DiskBox, snap.DiskLabels, snap.Disk);
            SetOn(MicSwitch, snap.MicEnabled);
            SetOn(SpkSwitch, snap.SpkEnabled);
            SetOn(DefaultSpkSwitch, snap.SetDefaultSpk);
            SetOn(VolSyncSwitch, snap.VolumeSync);
            SetOn(ToastSwitch, snap.ToastMirror);
            SetOn(PcStatsSwitch, snap.PcStats);
            SetOn(LightSwitch, snap.LightTheme);
            SetOn(UpsideSwitch, snap.UpsideDown);
            SetOn(AutoStartSwitch, snap.Autostart);
            SetOn(TraySwitch, snap.MinimizeToTray);
            if (Math.Abs(GainSlider.Value - snap.Gain) > 0.5)
            {
                GainSlider.Value = snap.Gain;
            }
            GainLabel.Text = snap.GainLabel;
            MicHint.Text = snap.MicHint;
            PcLine.Text = snap.PcLine;
            MicStatus.Text = snap.MicMuted ? "● 静音" : connected && snap.MicEnabled ? "● 正常" : "○ 关闭";
            SpkStatus.Text = snap.SpkMuted ? "● 静音" : connected && snap.SpkEnabled ? "● 正常" : "○ 关闭";
            MicMeter.Value = Clamp01(snap.MicPeak * 2.2);
            SpkMeter.Value = Clamp01(snap.SpkPeak * 2.2);
            PaneStatus.Text = connected ? "● 已连接" : snap.Connecting ? "● 正在连接..." : "○ 未连接";
            PaneHint.Text = connected ? $"{snap.Model} · USB / ADB" : "请连接 LX04";
            BarAudio.Text = (snap.AudioOk ? "●" : "○") + " 音频：" + (snap.AudioOk ? "正常" : "—");
            BarScreen.Text = "● 屏幕：" + snap.ScreenMode;
            BarToast.Text = (snap.ToastMirror ? "●" : "○") + " 弹窗同步：" + (snap.ToastMirror ? "已开启" : "关");
            if (!MonitorBox.IsDropDownOpen && !QualityBox.IsDropDownOpen && !DiskBox.IsDropDownOpen)
            {
                RenderDiag(snap);
                RenderHud(snap);
            }
        }
        finally
        {
            _applying = false;
        }
    }

    private static void SetOn(ToggleSwitch box, bool on)
    {
        if (box.IsOn != on)
        {
            box.IsOn = on;
        }
    }

    private static string? BoxText(object? item) =>
        item as string ?? (item as ComboBoxItem)?.Content?.ToString();

    private static void FillBox(ComboBox box, List<string> labels, string selected)
    {
        if (labels.Count == 0)
        {
            return;
        }
        if (box.IsDropDownOpen && box.Items.Count > 0)
        {
            return;
        }
        var same = box.Items.Count == labels.Count;
        if (same)
        {
            for (var i = 0; i < labels.Count; i++)
            {
                if (BoxText(box.Items[i]) != labels[i])
                {
                    same = false;
                    break;
                }
            }
        }
        if (!same)
        {
            box.Items.Clear();
            foreach (var label in labels)
            {
                box.Items.Add(label);
            }
        }
        var want = labels.Contains(selected) ? selected : labels[0];
        if (BoxText(box.SelectedItem) != want)
        {
            box.SelectedItem = want;
        }
    }

    private void RenderDiag(Snapshot snap)
    {
        DiagList.Children.Clear();
        foreach (var row in snap.Diagnostics)
        {
            var color = row.Status switch
            {
                "ok" => Color.FromArgb(255, 16, 137, 62),
                "warn" => Color.FromArgb(255, 157, 93, 0),
                "error" => Color.FromArgb(255, 196, 43, 28),
                _ => Color.FromArgb(255, 122, 122, 122),
            };
            var mark = row.Status switch
            {
                "ok" => "✓ ",
                "warn" => "⚠ ",
                "error" => "✕ ",
                _ => "○ ",
            };
            var block = new StackPanel { Spacing = 2 };
            block.Children.Add(new TextBlock
            {
                Text = mark + row.Label,
                Foreground = new SolidColorBrush(color),
            });
            if (!string.IsNullOrWhiteSpace(row.Hint) && row.Status is "warn" or "error")
            {
                block.Children.Add(new TextBlock { Text = row.Hint, Opacity = 0.7, TextWrapping = TextWrapping.Wrap });
            }
            DiagList.Children.Add(block);
        }
    }

    private void RenderHud(Snapshot snap)
    {
        var light = snap.Hud.Light;
        HudFrame.Background = new SolidColorBrush(ParseHex(light ? "#F4F6FA" : "#0B1220"));
        HudGrid.Children.Clear();
        var cards = snap.Hud.Cards;
        if (cards.Count == 0)
        {
            HudGrid.Children.Add(new TextBlock
            {
                Text = "800 × 480 预览",
                HorizontalAlignment = HorizontalAlignment.Center,
                VerticalAlignment = VerticalAlignment.Center,
                Foreground = new SolidColorBrush(ParseHex(light ? "#5B6B88" : "#8FA0BE")),
            });
            return;
        }
        var grid = new Grid { Margin = new Thickness(16) };
        for (var i = 0; i < 4; i++)
        {
            grid.ColumnDefinitions.Add(new ColumnDefinition());
        }
        for (var i = 0; i < cards.Count && i < 4; i++)
        {
            var card = cards[i];
            var panel = new Border
            {
                Margin = new Thickness(6),
                Padding = new Thickness(12),
                CornerRadius = new CornerRadius(6),
                Background = new SolidColorBrush(ParseHex(light ? "#FFFFFF" : "#141C2E")),
            };
            var stack = new StackPanel { Spacing = 4 };
            stack.Children.Add(new TextBlock
            {
                Text = card.Title ?? "",
                Foreground = new SolidColorBrush(ParseHex(card.TitleColor ?? (light ? "#5B6B88" : "#8FA0BE"))),
            });
            stack.Children.Add(new TextBlock
            {
                Text = card.Value ?? "—",
                FontSize = 28,
                FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
                Foreground = new SolidColorBrush(ParseHex(card.ValueColor ?? "#3DDC97")),
            });
            foreach (var sub in card.Subs.Take(2))
            {
                stack.Children.Add(new TextBlock { Text = sub, Opacity = 0.75, FontSize = 12 });
            }
            panel.Child = stack;
            Grid.SetColumn(panel, i);
            grid.Children.Add(panel);
        }
        HudGrid.Children.Add(grid);
    }

    private static Color ParseHex(string hex)
    {
        hex = hex.TrimStart('#');
        if (hex.Length < 6)
        {
            return Colors.Gray;
        }
        return Color.FromArgb(255,
            Convert.ToByte(hex[..2], 16),
            Convert.ToByte(hex[2..4], 16),
            Convert.ToByte(hex[4..6], 16));
    }

    private static double Clamp01(double v) => Math.Max(0, Math.Min(1, v));

    private void AddLog(string level, string line)
    {
        _logs.Add((level, DateTime.Now.ToString("HH:mm:ss") + "  " + level + "\n" + line));
        if (_logs.Count > 800)
        {
            _logs.RemoveRange(0, _logs.Count - 500);
        }
        _lastLog = DateTime.Now.ToString("HH:mm") + "  " + line;
        BarLog.Text = "最近日志 " + DateTime.Now.ToString("HH:mm");
        RefreshLogBox();
    }

    private void RefreshLogBox()
    {
        var want = _logFilter;
        var sb = new StringBuilder();
        foreach (var (level, line) in _logs)
        {
            if (want != "全部")
            {
                var key = want == "WARNING" ? "WARN" : want;
                if (!level.StartsWith(key, StringComparison.OrdinalIgnoreCase) && level != want)
                {
                    continue;
                }
            }
            sb.AppendLine(line);
            sb.AppendLine();
        }
        LogBox.Text = sb.ToString();
    }

    private async Task Call(string method, object? p = null)
    {
        try
        {
            var el = await _bridge.Call(method, p);
            if (el.TryGetProperty("result", out var result) && result.ValueKind == JsonValueKind.Object && result.TryGetProperty("connected", out _))
            {
                ApplySnapshot(ParseSnap(result));
            }
        }
        catch (Exception ex)
        {
            AddLog("ERROR", ex.Message);
        }
    }

    private async Task Set(string key, object? value)
    {
        if (_applying)
        {
            return;
        }
        await Call("set", new { key, value });
    }

    private async void Refresh_Click(object sender, RoutedEventArgs e) => await Call("refresh");
    private async void Connect_Click(object sender, RoutedEventArgs e) => await Call("connect", new { serial = _snap.Device });
    private async void Disconnect_Click(object sender, RoutedEventArgs e) => await Call("disconnect");
    private async void Diagnose_Click(object sender, RoutedEventArgs e) => await Call("diagnose");
    private async void MuteMic_Click(object sender, RoutedEventArgs e) => await Call("mute_mic");
    private async void MuteSpk_Click(object sender, RoutedEventArgs e) => await Call("mute_spk");
    private async void TestTone_Click(object sender, RoutedEventArgs e) => await Call("test_tone");
    private async void SpeakerTest_Click(object sender, RoutedEventArgs e) => await Call("speaker_test");
    private async void InstallVb_Click(object sender, RoutedEventArgs e) => await Call("install_vb");
    private async void InstallHifi_Click(object sender, RoutedEventArgs e) => await Call("install_hifi");
    private async void Afterburner_Click(object sender, RoutedEventArgs e) => await Call("afterburner");
    private async void UploadBg_Click(object sender, RoutedEventArgs e) => await Call("upload_bg");
    private async void HudReset_Click(object sender, RoutedEventArgs e) => await Call("hud", new { reset = true });
    private async void Watch_Click(object sender, RoutedEventArgs e) => await Call("mirror", new { on = false });
    private async void Mirror_Click(object sender, RoutedEventArgs e) => await Call("mirror", new { on = true });
    private async void MicSwitch_Toggled(object sender, RoutedEventArgs e) => await Set("micEnabled", MicSwitch.IsOn);
    private async void SpkSwitch_Toggled(object sender, RoutedEventArgs e) => await Set("spkEnabled", SpkSwitch.IsOn);
    private async void DefaultSpk_Toggled(object sender, RoutedEventArgs e) => await Set("setDefaultSpk", DefaultSpkSwitch.IsOn);
    private async void VolSync_Toggled(object sender, RoutedEventArgs e) => await Set("volumeSync", VolSyncSwitch.IsOn);
    private async void Toast_Toggled(object sender, RoutedEventArgs e) => await Set("toastMirror", ToastSwitch.IsOn);
    private async void PcStats_Toggled(object sender, RoutedEventArgs e) => await Set("pcStats", PcStatsSwitch.IsOn);
    private async void Light_Toggled(object sender, RoutedEventArgs e) => await Set("lightTheme", LightSwitch.IsOn);
    private async void Upside_Toggled(object sender, RoutedEventArgs e) => await Set("upsideDown", UpsideSwitch.IsOn);
    private async void Autostart_Toggled(object sender, RoutedEventArgs e) => await Set("autostart", AutoStartSwitch.IsOn);
    private async void TrayPref_Toggled(object sender, RoutedEventArgs e) => await Set("minimizeToTray", TraySwitch.IsOn);
    private async void Inject_Changed(object sender, SelectionChangedEventArgs e)
    {
        if (InjectBox.SelectedItem is string s)
        {
            await Set("inject", s);
        }
    }
    private async void Speaker_Changed(object sender, SelectionChangedEventArgs e)
    {
        if (SpeakerBox.SelectedItem is string s)
        {
            await Set("speaker", s);
        }
    }
    private async void Monitor_Changed(object sender, SelectionChangedEventArgs e)
    {
        if (MonitorBox.SelectedItem is string s)
        {
            await Set("monitor", s);
        }
    }
    private async void Quality_Changed(object sender, SelectionChangedEventArgs e)
    {
        if (QualityBox.SelectedItem is string s)
        {
            await Set("quality", s);
        }
    }
    private async void Disk_Changed(object sender, SelectionChangedEventArgs e)
    {
        if (DiskBox.SelectedItem is string s)
        {
            await Set("disk", s);
        }
    }
    private async void Gain_Changed(object sender, Microsoft.UI.Xaml.Controls.Primitives.RangeBaseValueChangedEventArgs e)
    {
        if (_applying)
        {
            return;
        }
        await Call("gain", new { value = GainSlider.Value });
    }

    private void Theme_Changed(object sender, SelectionChangedEventArgs e)
    {
        if (_applying || ThemeBox.SelectedItem is not ComboBoxItem item)
        {
            return;
        }
        ApplyTheme(item.Tag as string ?? "default");
    }

    internal static string ThemeFilePath() =>
        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "LX04-PC-Bridge", "shell-theme.txt");

    internal static string ReadShellTheme()
    {
        try
        {
            var tag = File.ReadAllText(ThemeFilePath()).Trim();
            return tag is "light" or "dark" or "default" ? tag : "default";
        }
        catch
        {
            return "default";
        }
    }

    private void ApplyTheme(string tag)
    {
        Root.RequestedTheme = tag switch
        {
            "light" => ElementTheme.Light,
            "dark" => ElementTheme.Dark,
            _ => ElementTheme.Default,
        };
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(ThemeFilePath())!);
            File.WriteAllText(ThemeFilePath(), tag);
        }
        catch
        {
        }
    }

    private void ApplySavedTheme()
    {
        var tag = ReadShellTheme();
        _applying = true;
        foreach (var item in ThemeBox.Items)
        {
            if (item is ComboBoxItem box && (box.Tag as string) == tag)
            {
                ThemeBox.SelectedItem = box;
                break;
            }
        }
        ApplyTheme(tag);
        _applying = false;
    }

    private void LogFilter_Changed(object sender, SelectionChangedEventArgs e)
    {
        if (LogFilter.SelectedItem is ComboBoxItem item)
        {
            _logFilter = item.Content?.ToString() ?? "全部";
            RefreshLogBox();
        }
    }

    private void LogClear_Click(object sender, RoutedEventArgs e)
    {
        _logs.Clear();
        RefreshLogBox();
    }

    private async void LogCopy_Click(object sender, RoutedEventArgs e)
    {
        var data = new Windows.ApplicationModel.DataTransfer.DataPackage();
        data.SetText(LogBox.Text);
        Windows.ApplicationModel.DataTransfer.Clipboard.SetContent(data);
        await Task.CompletedTask;
    }
}
