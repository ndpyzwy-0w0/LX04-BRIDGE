# LX04 PC Bridge

给小爱音箱触屏版 **LX04** 用的麦克风桥接：音箱里跑一个很小的 APK（目标远小于 300MB），用 **USB 数据线**连到 Windows 电脑。电脑上位机把音箱麦克风当成输入，音箱 800×480 屏幕当状态显示器。

## 它做什么

- 音箱采集双麦阵列里的麦克风，把 PCM 音频经 USB（ADB 隧道）送给电脑
- 电脑上位机把音频播放到指定输出设备。若安装 [VB-Audio Virtual Cable](https://vb-audio.com/Cable/)，其它软件可以把 `CABLE Output` 选成麦克风
- 音箱屏幕显示：USB 是否插上、是否连上上位机、电平、静音、采样率、丢帧

官方固件的 Micro USB **默认不能装第三方 APK**，也常被写成“不支持数据传输”。要用本项目，音箱需要已经能装普通 APK（社区官改 / 刷成 X04G / Lineage 等），并且使用 **能传数据的 Micro USB 线**（纯充电线不行）。

## 目录

| 路径 | 说明 |
|------|------|
| `app/` | LX04 上的 Android 8.1+ APK，无 AndroidX、无 Play 服务，体积按几 MB 设计 |
| `host/` | Windows 上位机（Python） |
| `protocol.md` | USB 上的 TCP 帧格式 |

默认端口：`17890`。上位机执行 `adb forward tcp:17890 tcp:17890` 后连 `127.0.0.1:17890`，音频和状态都走这条 USB 隧道，不依赖 Wi-Fi。

## 电脑准备

1. 安装 [Android SDK Platform-Tools](https://developer.android.com/tools/releases/platform-tools)（要有 `adb.exe`），或安装 Android Studio
2. Python 3.10+ 
3. 在 `host` 目录运行 `install_deps.bat`，或：

```text
pip install -r host/requirements.txt
```

4. （推荐）安装 VB-Audio Virtual Cable，这样微信 / 腾讯会议 / Discord 才能把 LX04 选成麦克风

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

在音箱屏幕上应看到「等待 USB」或「USB 已连接」。点屏幕下方可静音。

## 打开上位机

可运行 exe（不依赖本机 Python）：

```text
python build_host_exe.py
```

生成 `dist/LX04-PC-Bridge-Host.exe`（当前版）和带版本号的 `dist/LX04-PC-Bridge-Host-vN.exe`（不覆盖旧包）。双击仓库根目录的 `启动上位机.bat` 即可。

也可以直接跑源码：`host/start_host.bat`。

启动后：

1. 点 **刷新**，应出现 LX04 的 adb 序列号
2. **虚拟麦克风输出**优先选 `CABLE Input`（若已装虚拟声卡）
3. 点 **连接**
4. 音箱屏幕应变为「正在拾音」，对音箱说话，电脑电平条会动
5. 在会议软件里把麦克风选成 `CABLE Output`

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
