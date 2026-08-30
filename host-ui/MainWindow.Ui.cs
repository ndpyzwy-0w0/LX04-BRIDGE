using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;

namespace LX04.HostUi;

public sealed partial class MainWindow
{
    private NavigationView Nav = null!;
    private TextBlock PageTitle = null!;
    private TextBlock PageSub = null!;
    private TextBlock PaneStatus = null!;
    private TextBlock PaneHint = null!;
    private ScrollViewer OverviewPage = null!;
    private ScrollViewer AudioPage = null!;
    private ScrollViewer ScreenPage = null!;
    private ScrollViewer SettingsPage = null!;
    private Grid LogPage = null!;
    private InfoBar ConnectBar = null!;
    private TextBlock DeviceLine = null!;
    private TextBlock DeviceSub = null!;
    private Button RefreshBtn = null!;
    private Button ConnectBtn = null!;
    private Button DisconnectBtn = null!;
    private StackPanel DiagList = null!;
    private ProgressBar MicMeter = null!;
    private ProgressBar SpkMeter = null!;
    private ComboBox InjectBox = null!;
    private ComboBox SpeakerBox = null!;
    private ComboBox MonitorBox = null!;
    private ComboBox QualityBox = null!;
    private ComboBox DiskBox = null!;
    private ComboBox ThemeBox = null!;
    private ComboBox LogFilter = null!;
    private ToggleSwitch MicSwitch = null!;
    private ToggleSwitch SpkSwitch = null!;
    private ToggleSwitch DefaultSpkSwitch = null!;
    private ToggleSwitch VolSyncSwitch = null!;
    private ToggleSwitch ToastSwitch = null!;
    private ToggleSwitch PcStatsSwitch = null!;
    private ToggleSwitch LightSwitch = null!;
    private ToggleSwitch UpsideSwitch = null!;
    private ToggleSwitch AutoStartSwitch = null!;
    private ToggleSwitch TraySwitch = null!;
    private Slider GainSlider = null!;
    private TextBlock GainLabel = null!;
    private TextBlock MicHint = null!;
    private TextBlock MicStatus = null!;
    private TextBlock SpkStatus = null!;
    private TextBlock PcLine = null!;
    private Border HudFrame = null!;
    private Grid HudGrid = null!;
    private TextBox LogBox = null!;
    private TextBlock BarAudio = null!;
    private TextBlock BarScreen = null!;
    private TextBlock BarToast = null!;
    private TextBlock BarLog = null!;

    private void BuildUi()
    {
        Nav = new NavigationView
        {
            IsBackButtonVisible = NavigationViewBackButtonVisible.Collapsed,
            IsSettingsVisible = false,
            PaneDisplayMode = NavigationViewPaneDisplayMode.Left,
            OpenPaneLength = 200,
            IsPaneToggleButtonVisible = false,
        };
        Nav.MenuItems.Add(Item("总览", "overview", "\uE80F"));
        Nav.MenuItems.Add(Item("音频", "audio", "\uE8D6"));
        Nav.MenuItems.Add(Item("屏幕", "screen", "\uE7F4"));
        Nav.MenuItems.Add(Item("设置", "settings", "\uE713"));
        Nav.MenuItems.Add(Item("日志", "log", "\uE8A5"));
        PaneStatus = new TextBlock { Text = "○ 未连接", FontWeight = Microsoft.UI.Text.FontWeights.SemiBold, Margin = new Thickness(0, 8, 0, 0) };
        PaneHint = new TextBlock { Text = "请连接 LX04", Opacity = 0.7 };
        Nav.PaneFooter = new StackPanel
        {
            Padding = new Thickness(16, 8, 16, 16),
            Spacing = 2,
            Children =
            {
                new Border { Height = 1, Background = new SolidColorBrush(Windows.UI.Color.FromArgb(40, 128, 128, 128)) },
                PaneStatus,
                PaneHint,
            },
        };
        Nav.SelectionChanged += Nav_SelectionChanged;

        PageTitle = new TextBlock { FontSize = 22, FontWeight = Microsoft.UI.Text.FontWeights.SemiBold, Text = "总览" };
        PageSub = new TextBlock { Opacity = 0.7, Text = "连接状态与诊断", Margin = new Thickness(0, 0, 0, 12) };

        OverviewPage = BuildOverview();
        AudioPage = BuildAudio();
        ScreenPage = BuildScreen();
        SettingsPage = BuildSettings();
        LogPage = BuildLog();
        AudioPage.Visibility = Visibility.Collapsed;
        ScreenPage.Visibility = Visibility.Collapsed;
        SettingsPage.Visibility = Visibility.Collapsed;
        LogPage.Visibility = Visibility.Collapsed;

        var body = new Grid { Padding = new Thickness(20, 16, 20, 8) };
        body.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        body.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        var head = new StackPanel { Children = { PageTitle, PageSub } };
        var pages = new Grid();
        pages.Children.Add(OverviewPage);
        pages.Children.Add(AudioPage);
        pages.Children.Add(ScreenPage);
        pages.Children.Add(SettingsPage);
        pages.Children.Add(LogPage);
        Grid.SetRow(pages, 1);
        body.Children.Add(head);
        body.Children.Add(pages);
        Nav.Content = body;

        BarAudio = new TextBlock { Text = "○ 音频：—" };
        BarScreen = new TextBlock { Text = "○ 屏幕：状态监视" };
        BarToast = new TextBlock { Text = "○ 弹窗同步：关" };
        BarLog = new TextBlock { Opacity = 0.7, HorizontalAlignment = HorizontalAlignment.Right };
        var bar = new Grid { Padding = new Thickness(16, 6, 16, 6) };
        bar.Children.Add(new StackPanel
        {
            Orientation = Orientation.Horizontal,
            Spacing = 16,
            Children = { BarAudio, BarScreen, BarToast },
        });
        bar.Children.Add(BarLog);

        Root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        Root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        Root.Children.Add(Nav);
        Grid.SetRow(bar, 1);
        Root.Children.Add(bar);
        Nav.SelectedItem = Nav.MenuItems[0];
    }

    private static NavigationViewItem Item(string text, string tag, string glyph) =>
        new() { Content = text, Tag = tag, Icon = new FontIcon { Glyph = glyph } };

    private ScrollViewer BuildOverview()
    {
        ConnectBar = new InfoBar { IsOpen = true, IsClosable = false, Severity = InfoBarSeverity.Informational, Title = "未连接", Message = "请连接 LX04 设备后开始使用" };
        DeviceLine = new TextBlock { Text = "未检测到 LX04" };
        DeviceSub = new TextBlock { Text = "ADB · USB", Opacity = 0.7 };
        RefreshBtn = new Button { Content = "刷新设备" };
        RefreshBtn.Click += Refresh_Click;
        ConnectBtn = new Button { Content = "连接" };
        ConnectBtn.Click += Connect_Click;
        DisconnectBtn = new Button { Content = "断开连接", Visibility = Visibility.Collapsed };
        DisconnectBtn.Click += Disconnect_Click;
        DiagList = new StackPanel { Spacing = 6 };
        var diagnose = new Button { Content = "重新检测", HorizontalAlignment = HorizontalAlignment.Right };
        diagnose.Click += Diagnose_Click;
        var card = Card(new StackPanel
        {
            Spacing = 8,
            Children =
            {
                DeviceLine,
                DeviceSub,
                new StackPanel { Orientation = Orientation.Horizontal, Spacing = 8, Children = { RefreshBtn, ConnectBtn, DisconnectBtn } },
            },
        });
        return Scroll(new StackPanel
        {
            Spacing = 12,
            Children =
            {
                ConnectBar,
                Label("设备"),
                card,
                Label("连接诊断"),
                DiagList,
                diagnose,
            },
        });
    }

    private ScrollViewer BuildAudio()
    {
        MicStatus = new TextBlock { Text = "○ 未连接", HorizontalAlignment = HorizontalAlignment.Right };
        SpkStatus = new TextBlock { Text = "○ 未连接", HorizontalAlignment = HorizontalAlignment.Right };
        MicMeter = new ProgressBar { Minimum = 0, Maximum = 1, Height = 8 };
        SpkMeter = new ProgressBar { Minimum = 0, Maximum = 1, Height = 8 };
        InjectBox = new ComboBox { Header = "输出到", HorizontalAlignment = HorizontalAlignment.Stretch };
        InjectBox.SelectionChanged += Inject_Changed;
        SpeakerBox = new ComboBox { Header = "来源", HorizontalAlignment = HorizontalAlignment.Stretch };
        SpeakerBox.SelectionChanged += Speaker_Changed;
        MicSwitch = Switch("麦克风通路", MicSwitch_Toggled);
        SpkSwitch = Switch("扬声器通路", SpkSwitch_Toggled);
        DefaultSpkSwitch = Switch("设为默认播放", DefaultSpk_Toggled);
        VolSyncSwitch = Switch("同步系统音量", VolSync_Toggled);
        GainSlider = new Slider { Header = "麦克风增益", Minimum = 0, Maximum = 300, Value = 100 };
        GainSlider.ValueChanged += Gain_Changed;
        GainLabel = new TextBlock { Opacity = 0.7 };
        MicHint = new TextBlock { Opacity = 0.7 };
        var muteMic = new Button { Content = "静音麦克风" };
        muteMic.Click += MuteMic_Click;
        var test = new Button { Content = "试音" };
        test.Click += TestTone_Click;
        var muteSpk = new Button { Content = "静音扬声器" };
        muteSpk.Click += MuteSpk_Click;
        var spkTest = new Button { Content = "音箱试音" };
        spkTest.Click += SpeakerTest_Click;
        var vb = new Button { Content = "安装 VB-CABLE" };
        vb.Click += InstallVb_Click;
        var hifi = new Button { Content = "安装 Hi-Fi Cable" };
        hifi.Click += InstallHifi_Click;
        return Scroll(new StackPanel
        {
            Spacing = 12,
            Children =
            {
                Card(Col(
                    Row(Label("麦克风"), MicStatus),
                    Dim("LX04 双麦阵列 → Windows"),
                    MicMeter,
                    InjectBox,
                    MicSwitch,
                    GainSlider,
                    GainLabel,
                    MicHint,
                    Row(muteMic, test))),
                Card(Col(
                    Row(Label("扬声器"), SpkStatus),
                    Dim("Windows → LX04"),
                    SpkMeter,
                    SpeakerBox,
                    SpkSwitch,
                    DefaultSpkSwitch,
                    VolSyncSwitch,
                    Row(muteSpk, spkTest))),
                Row(vb, hifi),
            },
        });
    }

    private ScrollViewer BuildScreen()
    {
        HudGrid = new Grid();
        HudFrame = new Border
        {
            Width = 800,
            Height = 480,
            CornerRadius = new CornerRadius(6),
            BorderThickness = new Thickness(1),
            Child = HudGrid,
        };
        var box = new Viewbox { Stretch = Stretch.Uniform, HorizontalAlignment = HorizontalAlignment.Left, MaxWidth = 720, Child = HudFrame };
        MonitorBox = new ComboBox { Header = "显示器", HorizontalAlignment = HorizontalAlignment.Stretch };
        MonitorBox.SelectionChanged += Monitor_Changed;
        QualityBox = new ComboBox { Header = "镜像质量", HorizontalAlignment = HorizontalAlignment.Stretch };
        QualityBox.SelectionChanged += Quality_Changed;
        DiskBox = new ComboBox { Header = "监测磁盘", HorizontalAlignment = HorizontalAlignment.Stretch };
        DiskBox.SelectionChanged += Disk_Changed;
        ToastSwitch = Switch("系统弹窗", Toast_Toggled);
        PcStatsSwitch = Switch("音箱显示电脑状态", PcStats_Toggled);
        LightSwitch = Switch("音箱浅色", Light_Toggled);
        UpsideSwitch = Switch("吊装倒转屏幕", Upside_Toggled);
        PcLine = new TextBlock { Opacity = 0.7, TextWrapping = TextWrapping.Wrap };
        var watch = new Button { Content = "状态监视" };
        watch.Click += Watch_Click;
        var mirror = new Button { Content = "屏幕镜像" };
        mirror.Click += Mirror_Click;
        var reset = new Button { Content = "恢复默认样式" };
        reset.Click += HudReset_Click;
        var bg = new Button { Content = "上传背景" };
        bg.Click += UploadBg_Click;
        var ab = new Button { Content = "CPU 温度 / Afterburner" };
        ab.Click += Afterburner_Click;
        return Scroll(new StackPanel
        {
            Spacing = 12,
            Children = { box, Row(watch, mirror, ToastSwitch), MonitorBox, QualityBox, PcStatsSwitch, DiskBox, LightSwitch, UpsideSwitch, PcLine, Row(reset, bg, ab) },
        });
    }

    private ScrollViewer BuildSettings()
    {
        ThemeBox = new ComboBox { Header = "主题", HorizontalAlignment = HorizontalAlignment.Stretch };
        ThemeBox.Items.Add(new ComboBoxItem { Content = "浅色", Tag = "light" });
        ThemeBox.Items.Add(new ComboBoxItem { Content = "深色", Tag = "dark" });
        ThemeBox.Items.Add(new ComboBoxItem { Content = "跟随 Windows", Tag = "default" });
        ThemeBox.SelectionChanged += Theme_Changed;
        AutoStartSwitch = Switch("开机自启动", Autostart_Toggled);
        TraySwitch = Switch("关闭后最小化到托盘", TrayPref_Toggled);
        return Scroll(new StackPanel
        {
            Spacing = 16,
            Children =
            {
                Label("外观"),
                ThemeBox,
                Label("监控"),
                Dim("磁盘与 CPU 温度在「屏幕」页设置。"),
                Label("系统"),
                AutoStartSwitch,
                TraySwitch,
            },
        });
    }

    private Grid BuildLog()
    {
        LogFilter = new ComboBox { Width = 140 };
        LogFilter.Items.Add(new ComboBoxItem { Content = "全部", IsSelected = true });
        LogFilter.Items.Add(new ComboBoxItem { Content = "INFO" });
        LogFilter.Items.Add(new ComboBoxItem { Content = "WARNING" });
        LogFilter.Items.Add(new ComboBoxItem { Content = "ERROR" });
        LogFilter.SelectedIndex = 0;
        LogFilter.SelectionChanged += LogFilter_Changed;
        var copy = new Button { Content = "复制" };
        copy.Click += LogCopy_Click;
        var clear = new Button { Content = "清空" };
        clear.Click += LogClear_Click;
        LogBox = new TextBox
        {
            AcceptsReturn = true,
            IsReadOnly = true,
            TextWrapping = TextWrapping.Wrap,
            FontFamily = new FontFamily("Consolas"),
        };
        var top = new Grid();
        top.Children.Add(LogFilter);
        var right = new StackPanel { Orientation = Orientation.Horizontal, HorizontalAlignment = HorizontalAlignment.Right, Spacing = 8, Children = { copy, clear } };
        top.Children.Add(right);
        var grid = new Grid();
        grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        grid.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        grid.Children.Add(top);
        Grid.SetRow(LogBox, 1);
        grid.Children.Add(LogBox);
        return grid;
    }

    private static ScrollViewer Scroll(UIElement child) => new() { Content = child };
    private static TextBlock Label(string t) => new() { Text = t, FontWeight = Microsoft.UI.Text.FontWeights.SemiBold };
    private static TextBlock Dim(string t) => new() { Text = t, Opacity = 0.7 };
    private static Border Card(UIElement child) => new()
    {
        Padding = new Thickness(12),
        CornerRadius = new CornerRadius(6),
        Child = child,
    };
    private static StackPanel Col(params UIElement[] items)
    {
        var p = new StackPanel { Spacing = 8 };
        foreach (var i in items)
        {
            p.Children.Add(i);
        }
        return p;
    }
    private static StackPanel Row(params UIElement[] items)
    {
        var p = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 8 };
        foreach (var i in items)
        {
            p.Children.Add(i);
        }
        return p;
    }
    private static ToggleSwitch Switch(string header, RoutedEventHandler on)
    {
        var s = new ToggleSwitch { Header = header };
        s.Toggled += on;
        return s;
    }
}
