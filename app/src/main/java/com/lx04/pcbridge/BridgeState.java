package com.lx04.pcbridge;

final class BridgeState {
    volatile boolean usbConnected;
    volatile boolean usbAdb;
    volatile boolean clientConnected;
    volatile boolean recording;
    volatile boolean muted;
    volatile boolean permissionDenied;
    volatile float level;
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
