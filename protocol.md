# LX04 PC Bridge 协议（USB 数据线）

二进制小端帧，走 TCP。默认端口 **17890**。

电脑用 USB 连音箱后，上位机执行：

```text
adb forward tcp:17890 tcp:17890
adb forward tcp:17891 tcp:17891
```

然后连接 `127.0.0.1:17890`（音频、音量、状态、控制）和 `127.0.0.1:17891`（屏幕镜像）。两条隧道都走 USB 上的 ADB，不依赖 Wi-Fi。镜像不再占用控制通道，避免投屏时音量等操作被堵住。

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
| 0x09 | VIDEO | 电脑→音箱 **17891** | JPEG（800×480，屏幕镜像） |
| 0x0A | VIDEO_ACK | 音箱→电脑 **17891** | 空（收到一帧 VIDEO 立刻回，seq 与该帧相同） |

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
  "volume": 0.55,
  "lightTheme": false,
  "screenMirror": false,
  "hudStyle": {
    "rev": 1710000000000,
    "reset": false,
    "cards": [{"key": "cpu", "title": "CPU", "metric": "cpu", "subMetric": "cpuT", "titleColor": "#8FA0BE", "valueColor": "#3DDC97", "valueSize": 32, "subSize": 12}]
  }
}
```

## CONTROL JSON

```json
{"cmd": "mute"}
{"cmd": "unmute"}
{"cmd": "toggle_spk_mute"}
{"cmd": "upside_down", "on": true}
{"cmd": "light_theme", "on": true}
{"cmd": "hud_style", "rev": 1710000000000, "cards": [{"key": "cpu", "metric": "cpuT", "subMetric": "cores", "titleColor": "#8FA0BE", "valueColor": "#3DDC97", "valueSize": 32, "subSize": 12}]}
{"cmd": "hud_style", "reset": true, "rev": 1710000000001}
{"cmd": "ping"}
{"cmd": "volume", "level": 0.55}
{"cmd": "pc_stats", "cpu": 34, "cpuT": 59, "gpu": 12, "gpuT": 49, "gpuN": "RTX 4070 SUPER", "vram": 28, "gpuW": 32, "ram": 35, "ramU": 22.2, "ramT": 63.8, "disk": 42, "diskN": "D:", "diskU": 400, "diskT": 931, "netD": 1500, "netU": 120, "up": 3600, "cores": 24}
{"cmd": "mirror_info", "title": "1  1920×1080  主屏"}
```

`pc_stats` 由电脑每秒推一次，音箱屏幕画 CPU / GPU / 内存 / 磁盘。占用用打包进 EXE 的采集器 + 系统 API / 显卡驱动，不要求接收方再装 Python 或监控软件。`diskN` / `diskU` / `diskT` 是上位机所选盘符和已用/总量 GB。温度字段在读不到时省略（不要发假的 ACPI 27°C）。GPU 温度优先用本机 NVIDIA NVML；CPU 封装温度仅在本机已开 MSI Afterburner 时补充。上位机可打开 MSI 官网下载页或启动本机已安装的 Afterburner，但不随包分发。

`mute` / `unmute` / `toggle_mute` 只切麦克风。扬声器用 `mute_spk` / `unmute_spk` / `toggle_spk_mute`。STATUS 里 `micMuted` / `spkMuted` 分开报；`muted` 仍表示麦克风静音（兼容旧上位机）。`upside_down` 由上位机切换吊装倒转屏幕。`light_theme` 切换浅色/深色底；音箱从右侧滑出菜单进入「系统设置」也可改，两边通过 STATUS `lightTheme` 与 CONTROL `light_theme` 实时同步。`hud_style` 同步各板块标题、大字颜色、大字号（`valueSize`，默认 28）和小字号（`subSize`，默认 11），以及大字（`metric`）和小字（`subMetric`）监视的数据：cpu / cpuT / gpu / gpuT / gpuW / gpuFan / vram / ram / ramGB / disk / diskGB / diskIo / netD / netU / cores / gpuN；小字还可 `none` 不显示。每个板块下半空位可画折线：`chart` 默认开启，`chart: false` 关闭；`chartMetric` 选折线数据，省略则跟随大字。字号超出板块宽高时会自动缩小并裁切，不会画出格子。`rev` 为双方的样式版本，较大的覆盖较小的。音箱长按某一栏目可编辑，改动经 STATUS `hudStyle` 回传电脑；电脑预览的改动经 CONTROL 下发。两边实时同一套样式。音箱显示真实读数，预览只用示意数字。`reset: true` 恢复默认。未连接上位机时，音箱等待页有「重置样式」。

`PLAY` 是电脑正在播放的声音，送给音箱喇叭。与 `AUDIO`（音箱麦克风 → 电脑）方向相反。

`VIDEO` 走单独的 **17891** 通道，不和音频/音量/STATUS 挤在 17890 上。画面是 800×480 JPEG，音箱从右侧菜单选「屏幕镜像」开始投屏，选「状态监视」立刻停止抓屏。上位机「同步屏幕」选择投哪一块显示器，「码率」可选流畅 / 清晰 / 高清 / 最高。`mirror_info` 仍走 17890，只把显示器名称告诉音箱。音箱在 17891 上每收到一帧回 `VIDEO_ACK`，电脑等确认后再发下一帧，避免画面隧道里堆旧图。JPEG 大约 8–90KB，随码率变化。payload 上限 **256KB**。画面走 17891，电脑扬声器 PCM 仍走 17890，投屏时喇叭照常出声。
