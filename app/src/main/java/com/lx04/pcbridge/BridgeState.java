package com.lx04.pcbridge;

final class BridgeState {
    volatile boolean usbConnected;
    volatile boolean usbAdb;
    volatile boolean clientConnected;
    volatile boolean recording;
    volatile boolean muted;
    volatile boolean permissionDenied;
    volatile float level;
    volatile float playLevel;
    volatile float volume = 1f;
    volatile float gain = 1f;
    volatile long frames;
    volatile long dropped;
    volatile int sampleRate = 48000;
    volatile int channels = 1;
    volatile String audioSource = "";
    volatile String androidRelease = "";
    volatile String pcName = "";
    volatile String apkVersion = "";
    volatile String headline = "等待 USB";
    volatile String detail = "请用数据线连接电脑并打开 USB 调试";

    volatile boolean pcStatsValid;
    volatile long pcStatsAt;
    volatile float pcCpu;
    volatile float pcCpuTemp = Float.NaN;
    volatile float pcGpu = Float.NaN;
    volatile float pcGpuTemp = Float.NaN;
    volatile float pcVram = Float.NaN;
    volatile float pcGpuWatts = Float.NaN;
    volatile float pcGpuFan = Float.NaN;
    volatile String pcGpuName = "";
    volatile float pcRam;
    volatile float pcRamUsed;
    volatile float pcRamTotal;
    volatile float pcDisk;
    volatile float pcDiskIo = Float.NaN;
    volatile float pcNetDown;
    volatile float pcNetUp;
    volatile long pcUptime;
    volatile int pcCores;

    boolean hasPcStats() {
        return pcStatsValid && clientConnected && pcStatsAt != 0
                && android.os.SystemClock.elapsedRealtime() - pcStatsAt < 4000;
    }

    String formatLink() {
        if (!usbConnected) {
            return "USB 未连接";
        }
        if (usbAdb) {
            return "USB ADB";
        }
        return "USB 已插入";
    }

    String formatAudio() {
        String source = audioSource == null || audioSource.isEmpty() ? "" : " · " + audioSource;
        return sampleRate / 1000 + "kHz / 16bit / "
                + (channels == 1 ? "单声道" : channels + "声道") + source;
    }
}
