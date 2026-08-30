using System.Text.Json;
using System.Text.Json.Serialization;

namespace LX04.HostUi;

public sealed class Snapshot
{
    public bool Connected { get; set; }
    public bool Connecting { get; set; }
    public bool Reviving { get; set; }
    public string Headline { get; set; } = "未连接";
    public string Detail { get; set; } = "";
    public string PcLine { get; set; } = "";
    public List<string> Devices { get; set; } = new();
    public string Device { get; set; } = "";
    public List<string> DeviceLabels { get; set; } = new();
    public bool Adb { get; set; }
    public string Model { get; set; } = "LX04";
    public string Android { get; set; } = "";
    public string Apk { get; set; } = "";
    public int Elapsed { get; set; }
    public bool MicEnabled { get; set; }
    public bool SpkEnabled { get; set; }
    public bool SetDefaultSpk { get; set; }
    public bool VolumeSync { get; set; }
    public bool PcStats { get; set; }
    public bool UpsideDown { get; set; }
    public bool LightTheme { get; set; }
    public bool ToastMirror { get; set; }
    public bool Autostart { get; set; }
    public bool MinimizeToTray { get; set; }
    public string Inject { get; set; } = "";
    public List<string> InjectLabels { get; set; } = new();
    public string Speaker { get; set; } = "";
    public List<string> SpeakerLabels { get; set; } = new();
    public string Disk { get; set; } = "";
    public List<string> DiskLabels { get; set; } = new();
    public string Monitor { get; set; } = "";
    public List<string> MonitorLabels { get; set; } = new();
    public string Quality { get; set; } = "";
    public List<string> QualityLabels { get; set; } = new();
    public string MicHint { get; set; } = "";
    public double Gain { get; set; }
    public string GainLabel { get; set; } = "";
    public bool MicMuted { get; set; }
    public bool SpkMuted { get; set; }
    public double MicPeak { get; set; }
    public double SpkPeak { get; set; }
    public bool VbCable { get; set; }
    public bool HifiCable { get; set; }
    public bool AudioOk { get; set; }
    public bool VideoOk { get; set; }
    public bool ToastOk { get; set; }
    public bool MirrorOn { get; set; }
    public bool ToastOn { get; set; }
    public string ScreenMode { get; set; } = "状态监视";
    public HudState Hud { get; set; } = new();
    public List<DiagRow> Diagnostics { get; set; } = new();
}

public sealed class HudState
{
    public bool Light { get; set; }
    public int Rev { get; set; }
    public List<HudCard> Cards { get; set; } = new();
}

public sealed class HudCard
{
    public string? Key { get; set; }
    public string? Title { get; set; }
    public string? Metric { get; set; }
    public string? Value { get; set; }
    public List<string> Subs { get; set; } = new();
    public string? TitleColor { get; set; }
    public string? ValueColor { get; set; }
    public bool Chart { get; set; } = true;
}

public sealed class DiagRow
{
    public string Id { get; set; } = "";
    public string Label { get; set; } = "";
    public string Status { get; set; } = "idle";
    public string Hint { get; set; } = "";
}

internal static class JsonOpts
{
    public static readonly JsonSerializerOptions Options = new()
    {
        PropertyNameCaseInsensitive = true,
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    };
}
