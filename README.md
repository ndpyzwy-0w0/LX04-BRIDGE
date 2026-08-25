# LX04 PC Bridge

给小爱音箱触屏版 **LX04** 用的麦克风 + 扬声器桥接：音箱里跑一个很小的 APK（目标远小于 300MB），用 **USB 数据线**连到 Windows 电脑。电脑上位机把音箱麦克风当成输入，把电脑正在播放的声音送到音箱喇叭，音箱 800×480 屏幕当状态显示器。

## 它做什么

- 音箱采集双麦阵列里的麦克风，把 PCM 音频经 USB（ADB 隧道）送给电脑
- 电脑上位机把麦克风灌进 [VB-CABLE](https://vb-audio.com/Cable/)，其它软件把 `CABLE Output` 选成麦克风
- 电脑正在播放的声音经第二根虚拟线 [Hi-Fi Cable](https://vb-audio.com/Cable/) 环回，再送到音箱喇叭
- 音箱屏幕显示：USB 状态、电脑资源占用、麦克风/扬声器可分别静音；从屏幕右侧向左滑出菜单，可进「系统设置」切换深色/浅色，与上位机「浅色」开关同步；上位机也可切换浅色/深色并预览 800×480 样式（每个格子可分别选大字和小字监视哪项数据、改标题、颜色和字号）；音箱上长按某一栏目也能编辑，与电脑完全同步；字不会画出格子；未连接时音箱上可点「重置样式」
- 连接后屏幕同时显示电脑 CPU / GPU 温度和使用率、内存、所选磁盘占用、网速（上位机可关、可选监测哪块盘）

官方固件的 Micro USB **默认不能装第三方 APK**，也常被写成“不支持数据传输”。要用本项目，音箱需要已经能装普通 APK（社区官改 / 刷成 X04G / Lineage 等），并且使用 **能传数据的 Micro USB 线**（纯充电线不行）。

## 目录

| 路径 | 说明 |
|------|------|
| `app/` | LX04 上的 Android 8.1+ APK，无 AndroidX、无 Play 服务，体积按几 MB 设计 |
| `host/` | Windows 上位机（Python） |
| `protocol.md` | USB 上的 TCP 帧格式 |

默认端口：`17890`。上位机执行 `adb forward tcp:17890 tcp:17890` 后连 `127.0.0.1:17890`，音频和状态都走这条 USB 隧道，不依赖 Wi-Fi。

## 电脑准备

1. Windows 10/11 64 位（可开着安全启动）
2. 官方 **VB-CABLE** 虚拟声卡（捐赠软件，来源 [www.vb-cable.com](https://www.vb-cable.com/)）
   - 发行包里带未修改的 `host/vbcable/`（`VBCABLE_Driver_Pack45.zip`）
   - 或以管理员运行 `host/vbcable/pack/VBCABLE_Setup_x64.exe`，**然后重启**
3. 要把电脑音乐/视频接到音箱喇叭，再装官方 **Hi-Fi Cable**（同样来自 VB-Audio，和 VB-CABLE 不是同一根线）
   - 连接时上位机会提示安装；或打开 [vb-audio.com](https://vb-audio.com/Cable/) 下载 `HiFiCableAsioBridgeSetup`
   - **装完后重启**
4. 上位机已内置 adb，不需要再装 Android SDK 也能连音箱

VB-CABLE 装好后，Windows 声音设置里会出现：

- **CABLE Input**：给上位机灌麦克风（不要设成电脑扬声器）
- **CABLE Output**：给微信 / QQ 当麦克风
- **Hi-Fi Cable Input**：连接后作为系统播放设备，声音进音箱喇叭

觉得 VB-CABLE / Hi-Fi Cable 好用请向作者捐赠。商业批量分发请看 [VB-Audio 授权说明](https://vb-audio.com/Services/licensing.htm)。

本仓库电脑上如果还没有 Android Studio / SDK，需要先装才能编译出 APK。

## 编译 APK

用 Android Studio 打开本仓库根目录（JDK 17+，本机是 JDK 21 也可以），执行 **Build > Build APK(s)**。命令行则是：

```text
gradlew.bat :app:assembleDebug
```

产物大约在：

```text
app/build/outputs/apk/debug/app-debug.apk
```

构建脚本会检查 APK 是否超过 **300MB**；正常包只有几 MB，不会接近上限。不要往 APK 里塞模型、视频或完整 JDK。

## 装到音箱

1. 音箱打开 **USB 调试**
2. 用数据线连电脑，设备管理器里应能看到 ADB 设备
3. 运行 `host/install_apk.bat`，或：

```text
adb install -r app/build/outputs/apk/debug/*.apk
adb shell pm grant com.lx04.pcbridge android.permission.RECORD_AUDIO
adb shell am start -n com.lx04.pcbridge/.MainActivity
```

在音箱屏幕上应看到 USB 指示和电脑状态卡片。下方可分别静音麦克风或扬声器。

## 打开上位机

可运行 exe（不依赖本机 Python）：

```text
python build_host_exe.py
```

生成 `dist/LX04-PC-Bridge-Host.exe`（只保留当前这一份，旧版用 git 回退）。双击仓库根目录的 `启动上位机.bat` 即可。

也可以直接跑源码：`host/start_host.bat`。

启动后：

1. 点 **刷新**，应出现 LX04 的 adb 序列号
2. 若尚未安装 VB-CABLE，点 **连接** 时会打开官方安装程序（需管理员）。装完后重启，再打开上位机
3. 点 **连接**
4. 音箱屏幕应变为「电脑扬声器 → 音箱」或「正在拾音」，对音箱说话，电脑麦克风电平条会动
5. 点 **音箱试音**，音箱喇叭应能听到「嘀」
6. 在微信 / QQ / 语音输入里把麦克风选成 **CABLE Output**（或「麦克风 (VB-Audio Virtual Cable)」）。彻底退出再打开这些软件，避免缓存旧设备
7. 电脑里的音乐/视频会从音箱出声（需已安装 Hi-Fi Cable 并重启）。断开连接后，系统扬声器会改回原来的设备

从源码跑上位机：先 `pip install -r host/requirements.txt`，再 `host/start_host.bat`。

## 电脑状态怎么来的

上位机每秒采一次，经 USB 推到音箱。**发给别人只需要 `LX04-PC-Bridge-Host.exe`，不必装 Python、不必装 Afterburner。**

| 项目 | 来源 | 分发时要不要额外东西 |
|------|------|----------------------|
| CPU / 内存占用、磁盘容量、网速、开机时长 | 打进 EXE 的 `psutil`，没有则退回 Windows API | 不用 |
| 磁盘 IO、部分 ACPI 温度、核显占用 | 系统自带 PDH | 不用 |
| NVIDIA 占用 / 温度 / 功耗 / 风扇 | 本机显卡驱动里的 `nvml.dll` | 有 NVIDIA 驱动即可，不随 EXE 带 DLL |
| AMD 占用 / 温度 | 本机显卡驱动里的 `atiadlxx.dll` | 有 AMD 驱动即可 |
| CPU 封装温度 | 若本机开着 MSI Afterburner，读它的共享内存 | **可选**。上位机有「CPU 温度 / Afterburner」按钮：已安装则启动，否则打开 [MSI 官网](https://www.msi.com/Landing/afterburner)。没有就省略温度，不显示假的 27°C |

不要把 Afterburner、HWiNFO、LibreHardwareMonitor 打进安装包。读不到的温度字段直接不发。

## 硬件与系统

| 项目 | LX04 |
|------|------|
| 芯片 | MT8167，约 1GB 内存 |
| 屏幕 | 3.97 寸，800×480，横屏 |
| 麦克风 | 顶部双麦 |
| 接口 | Micro USB（刷机/开调试后可走数据） |
| 系统 | 原版偏 Android 8.1；国际版 X04G 为 Android 10。本 APK `minSdk 26`，两种都能装 |

原版小爱若独占麦克风，可能录到静音。改版 ROM / 关掉语音助手后最稳。

## 体积约束

- APK 硬限制：≤ 300MB（Gradle 超限会失败）
- 实际：不引入大型依赖，release + minify 预期 **&lt; 5MB**
