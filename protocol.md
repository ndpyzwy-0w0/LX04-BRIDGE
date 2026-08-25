# LX04 PC Bridge 协议（USB 数据线）

二进制小端帧，走 TCP。默认端口 **17890**。

电脑用 USB 连音箱后，上位机执行：

```text
adb forward tcp:17890 tcp:17890
```

然后连接 `127.0.0.1:17890`。整条音频和状态都走 USB 上的 ADB 隧道，不依赖 Wi-Fi。

## 帧头 16 字节

| 偏移 | 类型 | 说明 |
|------|------|------|
| 0 | 4s | 魔数 `LXB1` |
| 4 | u8 | 消息类型 |
| 5 | u8 | 标志（bit0=静音） |
| 6 | u16 | 序号 |
| 8 | u32 | 设备 `elapsedRealtime` 毫秒 |
| 12 | u32 | payload 长度 |

## 类型

| 值 | 名称 | 方向 | payload |
|----|------|------|---------|
| 0x01 | HELLO | 音箱→电脑 | UTF-8 JSON |
| 0x02 | HELLO_ACK | 电脑→音箱 | UTF-8 JSON |
| 0x03 | AUDIO | 音箱→电脑 | PCM S16LE |
| 0x04 | STATUS | 音箱→电脑 | UTF-8 JSON |
| 0x05 | CONTROL | 电脑→音箱 | UTF-8 JSON |
| 0x06 | PING | 双向 | 空 |
| 0x07 | PONG | 双向 | 空 |
| 0x08 | PLAY | 电脑→音箱 | PCM S16LE 48 kHz 立体声 |

## HELLO JSON

```json
{
  "device": "LX04",
  "model": "Xiaomi LX04",
  "android": "8.1.0",
  "sampleRate": 48000,
  "channels": 1,
  "bits": 16,
  "encoding": "pcm_s16le",
  "port": 17890
}
```

## STATUS JSON

```json
{
  "usbConnected": true,
  "usbAdb": true,
  "recording": true,
  "muted": false,
  "micMuted": false,
  "spkMuted": false,
  "level": 0.42,
  "frames": 1200,
  "dropped": 0,
  "sampleRate": 48000,
  "channels": 1,
  "playLevel": 0.18,
  "volume": 0.55
}
```

## CONTROL JSON

```json
{"cmd": "mute"}
{"cmd": "unmute"}
{"cmd": "toggle_spk_mute"}
{"cmd": "upside_down", "on": true}
{"cmd": "light_theme", "on": true}
{"cmd": "hud_style", "cards": [{"key": "cpu", "titleColor": "#8FA0BE", "valueColor": "#3DDC97"}]}
{"cmd": "hud_style", "reset": true}
{"cmd": "ping"}
{"cmd": "volume", "level": 0.55}
{"cmd": "pc_stats", "cpu": 34, "cpuT": 59, "gpu": 12, "gpuT": 49, "gpuN": "RTX 4070 SUPER", "vram": 28, "gpuW": 32, "ram": 35, "ramU": 22.2, "ramT": 63.8, "disk": 42, "diskN": "D:", "diskU": 400, "diskT": 931, "netD": 1500, "netU": 120, "up": 3600, "cores": 24}
```

`pc_stats` 由电脑每秒推一次，音箱屏幕画 CPU / GPU / 内存 / 磁盘。占用用打包进 EXE 的采集器 + 系统 API / 显卡驱动，不要求接收方再装 Python 或监控软件。`diskN` / `diskU` / `diskT` 是上位机所选盘符和已用/总量 GB。温度字段在读不到时省略（不要发假的 ACPI 27°C）。GPU 温度优先用本机 NVIDIA NVML；CPU 封装温度仅在本机已开 MSI Afterburner 时补充。上位机可打开 MSI 官网下载页或启动本机已安装的 Afterburner，但不随包分发。

`mute` / `unmute` / `toggle_mute` 只切麦克风。扬声器用 `mute_spk` / `unmute_spk` / `toggle_spk_mute`。STATUS 里 `micMuted` / `spkMuted` 分开报；`muted` 仍表示麦克风静音（兼容旧上位机）。`upside_down` 由上位机切换吊装倒转屏幕。`light_theme` 切换浅色/深色底。`hud_style` 同步各板块标题字母和颜色（音箱仍显示真实占用，不用预览里填的数字）。`reset: true` 恢复默认配色。未连接上位机时，音箱等待页有「重置样式」。

`PLAY` 是电脑正在播放的声音，送给音箱喇叭。与 `AUDIO`（音箱麦克风 → 电脑）方向相反。
