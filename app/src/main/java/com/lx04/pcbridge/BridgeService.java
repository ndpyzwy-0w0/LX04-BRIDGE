package com.lx04.pcbridge;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.media.AudioManager;
import android.os.IBinder;
import android.os.PowerManager;
import android.os.SystemClock;

import org.json.JSONObject;

public class BridgeService extends Service {
    public static final BridgeState STATE = new BridgeState();

    private AudioCapture capture;
    private AudioPlayback playback;
    private TcpBridgeServer server;
    private UsbMonitor usbMonitor;
    private PowerManager.WakeLock wakeLock;
    private long lastAudioMs;
    private static AudioManager audioManager;

    @Override
    public void onCreate() {
        super.onCreate();
        STATE.androidRelease = android.os.Build.VERSION.RELEASE;
        STATE.apkVersion = AppVersion.read(this);
        STATE.upsideDown = DisplayPrefs.isUpsideDown(this);
        STATE.lightTheme = DisplayPrefs.isLightTheme(this);
        DisplayPrefs.loadHudStyle(this, STATE.hudStyle);
        startAsForeground();
        PowerManager pm = (PowerManager) getSystemService(POWER_SERVICE);
        if (pm != null) {
            wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "lx04:bridge");
            wakeLock.setReferenceCounted(false);
            wakeLock.acquire();
        }
        capture = new AudioCapture(this::onAudio);
        playback = new AudioPlayback();
        audioManager = (AudioManager) getSystemService(AUDIO_SERVICE);
        server = new TcpBridgeServer(STATE, new TcpBridgeServer.Callbacks() {
            @Override
            public void prepareForClient() {
            }

            @Override
            public void onClient(boolean connected, String helloAckName) {
                STATE.clientConnected = connected;
                STATE.pcName = helloAckName == null ? "" : helloAckName;
                if (!connected) {
                    STATE.pcStatsValid = false;
                }
                if (connected) {
                    playback.start();
                    if (audioManager != null) {
                        audioManager.setStreamMute(AudioManager.STREAM_MUSIC, false);
                    }
                    refreshHeadline();
                } else {
                    stopMic();
                    playback.stop();
                    refreshHeadline();
                }
            }

            @Override
            public void onPlay(byte[] pcm, boolean muted) {
                if (playback != null) {
                    playback.push(pcm, muted || STATE.spkMuted);
                    STATE.playLevel = playback.getPeak();
                }
            }

            @Override
            public void onControl(JSONObject json) {
                String cmd = json.optString("cmd", "");
                if ("gain".equals(cmd)) {
                    STATE.gain = (float) json.optDouble("gain", 1.0);
                    if (STATE.gain < 0f) {
                        STATE.gain = 0f;
                    } else if (STATE.gain > 4f) {
                        STATE.gain = 4f;
                    }
                } else if ("mute".equals(cmd) || "mute_mic".equals(cmd)) {
                    STATE.micMuted = true;
                } else if ("unmute".equals(cmd) || "unmute_mic".equals(cmd)) {
                    STATE.micMuted = false;
                } else if ("toggle_mute".equals(cmd) || "toggle_mic_mute".equals(cmd)) {
                    STATE.micMuted = !STATE.micMuted;
                } else if ("mute_spk".equals(cmd)) {
                    STATE.spkMuted = true;
                } else if ("unmute_spk".equals(cmd)) {
                    STATE.spkMuted = false;
                } else if ("toggle_spk_mute".equals(cmd)) {
                    STATE.spkMuted = !STATE.spkMuted;
                } else if ("start_mic".equals(cmd)) {
                    startMic();
                } else if ("stop_mic".equals(cmd)) {
                    stopMic();
                } else if ("volume".equals(cmd)) {
                    setMusicVolume((float) json.optDouble("level", STATE.volume));
                } else if ("upside_down".equals(cmd)) {
                    STATE.upsideDown = json.optBoolean("on", !STATE.upsideDown);
                    DisplayPrefs.setUpsideDown(BridgeService.this, STATE.upsideDown);
                    return;
                } else if ("light_theme".equals(cmd)) {
                    STATE.lightTheme = json.optBoolean("on", !STATE.lightTheme);
                    DisplayPrefs.setLightTheme(BridgeService.this, STATE.lightTheme);
                    return;
                } else if ("hud_style".equals(cmd)) {
                    applyHudStyle(json);
                    return;
                } else if ("pc_stats".equals(cmd)) {
                    applyPcStats(json);
                    return;
                }
                refreshHeadline();
            }
        });
        usbMonitor = new UsbMonitor(this, (connected, adb) -> {
            STATE.usbConnected = connected;
            STATE.usbAdb = adb;
            refreshHeadline();
        });
        usbMonitor.start();
        server.start();
        Watchdog.schedule(this);
        refreshHeadline();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        Watchdog.schedule(this);
        if (intent != null && "toggle_mute".equals(intent.getAction())) {
            STATE.micMuted = !STATE.micMuted;
            refreshHeadline();
        }
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        Watchdog.schedule(this);
        if (usbMonitor != null) {
            usbMonitor.stop();
        }
        if (server != null) {
            server.stop();
        }
        stopMic();
        if (playback != null) {
            playback.stop();
        }
        if (wakeLock != null && wakeLock.isHeld()) {
            wakeLock.release();
        }
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    public static void toggleMicMute() {
        STATE.micMuted = !STATE.micMuted;
        refreshHeadlineStatic();
    }

    public static void toggleSpkMute() {
        STATE.spkMuted = !STATE.spkMuted;
        refreshHeadlineStatic();
    }

    public static void resetHudStyle(android.content.Context context) {
        STATE.hudStyle.clear();
        STATE.lightTheme = false;
        if (context != null) {
            DisplayPrefs.clearHudStyle(context);
            DisplayPrefs.setLightTheme(context, false);
        }
    }

    private void applyHudStyle(JSONObject json) {
        if (json.optBoolean("reset", false)) {
            STATE.hudStyle.clear();
            DisplayPrefs.clearHudStyle(this);
            return;
        }
        STATE.hudStyle.applyJson(json);
        JSONObject store = new JSONObject();
        try {
            if (json.has("cards")) {
                store.put("cards", json.get("cards"));
            }
        } catch (Exception ignored) {
        }
        DisplayPrefs.setHudStyleJson(this, store.toString());
    }

    private static void refreshHeadlineStatic() {
        if (!STATE.clientConnected) {
            return;
        }
        STATE.headline = muteHeadline();
    }

    private static String muteHeadline() {
        if (STATE.micMuted && STATE.spkMuted) {
            return "麦和喇叭已静音";
        }
        if (STATE.micMuted) {
            return "麦克风已静音";
        }
        if (STATE.spkMuted) {
            return "扬声器已静音";
        }
        if (STATE.recording) {
            return "正在拾音";
        }
        return "电脑扬声器 → 音箱";
    }

    public static float musicVolume() {
        AudioManager am = audioManager;
        if (am == null) {
            return STATE.volume;
        }
        int max = am.getStreamMaxVolume(AudioManager.STREAM_MUSIC);
        if (max <= 0) {
            return STATE.volume;
        }
        STATE.volume = am.getStreamVolume(AudioManager.STREAM_MUSIC) / (float) max;
        return STATE.volume;
    }

    private void setMusicVolume(float level) {
        if (level < 0f) {
            level = 0f;
        } else if (level > 1f) {
            level = 1f;
        }
        AudioManager am = audioManager;
        if (am == null) {
            am = (AudioManager) getSystemService(AUDIO_SERVICE);
            audioManager = am;
        }
        if (am == null) {
            return;
        }
        int max = am.getStreamMaxVolume(AudioManager.STREAM_MUSIC);
        if (max <= 0) {
            return;
        }
        int index = Math.round(level * max);
        if (index < 0) {
            index = 0;
        } else if (index > max) {
            index = max;
        }
        am.setStreamVolume(AudioManager.STREAM_MUSIC, index, 0);
        STATE.volume = index / (float) max;
    }

    private static void applyPcStats(JSONObject json) {
        STATE.pcStatsValid = true;
        STATE.pcStatsAt = SystemClock.elapsedRealtime();
        STATE.pcCpu = (float) json.optDouble("cpu", 0);
        STATE.pcCpuTemp = optNum(json, "cpuT");
        STATE.pcGpu = optNum(json, "gpu");
        STATE.pcGpuTemp = optNum(json, "gpuT");
        STATE.pcVram = optNum(json, "vram");
        STATE.pcGpuWatts = optNum(json, "gpuW");
        STATE.pcGpuFan = optNum(json, "gpuFan");
        String gpuName = json.optString("gpuN", "");
        if (!gpuName.isEmpty()) {
            STATE.pcGpuName = gpuName;
        }
        STATE.pcRam = (float) json.optDouble("ram", 0);
        STATE.pcRamUsed = (float) json.optDouble("ramU", 0);
        STATE.pcRamTotal = (float) json.optDouble("ramT", 0);
        STATE.pcDisk = (float) json.optDouble("disk", 0);
        STATE.pcDiskUsed = (float) json.optDouble("diskU", 0);
        STATE.pcDiskTotal = (float) json.optDouble("diskT", 0);
        STATE.pcDiskIo = optNum(json, "diskIo");
        String diskName = json.optString("diskN", "");
        if (!diskName.isEmpty()) {
            STATE.pcDiskName = diskName;
        }
        STATE.pcNetDown = (float) json.optDouble("netD", 0);
        STATE.pcNetUp = (float) json.optDouble("netU", 0);
        STATE.pcUptime = json.optLong("up", 0);
        STATE.pcCores = json.optInt("cores", 0);
    }

    private static float optNum(JSONObject json, String key) {
        if (!json.has(key) || json.isNull(key)) {
            return Float.NaN;
        }
        return (float) json.optDouble(key, Double.NaN);
    }

    private void startMic() {
        if (!AudioCapture.hasMicPermission(this)) {
            STATE.permissionDenied = true;
            STATE.recording = false;
            refreshHeadline();
            return;
        }
        STATE.permissionDenied = false;
        if (capture.start()) {
            STATE.recording = true;
            STATE.sampleRate = capture.getSampleRate();
            STATE.channels = capture.getChannels();
            STATE.audioSource = capture.getSourceName();
            android.media.AudioManager am =
                    (android.media.AudioManager) getSystemService(AUDIO_SERVICE);
            if (am != null) {
                am.setMicrophoneMute(false);
                am.requestAudioFocus(null, android.media.AudioManager.STREAM_MUSIC,
                        android.media.AudioManager.AUDIOFOCUS_GAIN);
            }
        } else {
            STATE.recording = false;
            STATE.headline = "麦克风打开失败";
            STATE.detail = "请确认已授权录音，且小爱未独占麦克风";
            return;
        }
        refreshHeadline();
    }

    private void stopMic() {
        if (capture != null) {
            capture.stop();
        }
        STATE.recording = false;
        STATE.level = 0f;
    }

    private void onAudio(byte[] pcm, int length, float peak) {
        STATE.level = STATE.level * 0.72f + peak * 0.28f;
        STATE.frames++;
        lastAudioMs = SystemClock.elapsedRealtime();
        if (STATE.micMuted) {
            java.util.Arrays.fill(pcm, 0, length, (byte) 0);
            STATE.level = 0f;
        }
        if (server != null) {
            server.sendAudio(pcm, length, STATE.micMuted);
        }
        if (STATE.frames % 25 == 0) {
            refreshHeadline();
        }
    }

    private void refreshHeadline() {
        if (STATE.permissionDenied) {
            STATE.headline = "需要麦克风权限";
            STATE.detail = "请授权后重新打开本应用";
            return;
        }
        if (!STATE.usbConnected) {
            STATE.headline = "等待 USB";
            STATE.detail = "用能传数据的 Micro USB 线连接电脑";
            return;
        }
        if (!STATE.clientConnected) {
            STATE.headline = "USB 已连接";
            STATE.detail = STATE.usbAdb
                    ? "等待上位机（adb forward 17890）"
                    : "请打开 USB 调试后启动电脑上位机";
            return;
        }
        if (STATE.micMuted || STATE.spkMuted) {
            STATE.headline = muteHeadline();
        } else if (STATE.recording) {
            STATE.headline = "正在拾音";
        } else {
            STATE.headline = "电脑扬声器 → 音箱";
        }
        String pc = STATE.pcName.isEmpty() ? "电脑" : STATE.pcName;
        long silence = lastAudioMs == 0 ? 0 : SystemClock.elapsedRealtime() - lastAudioMs;
        STATE.detail = pc + " · " + STATE.formatLink() + " · " + STATE.formatAudio()
                + " · 增益 " + Math.round(STATE.gain * 100) + "%"
                + (silence > 1500 && STATE.recording ? " · 无声音输入" : "");
    }

    private void startAsForeground() {
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (nm != null) {
            NotificationChannel channel = new NotificationChannel(
                    "bridge", "LX04 Bridge", NotificationManager.IMPORTANCE_DEFAULT);
            channel.setShowBadge(false);
            nm.createNotificationChannel(channel);
        }
        Intent launch = new Intent(this, MainActivity.class);
        PendingIntent pi = PendingIntent.getActivity(this, 0, launch,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification notification = new Notification.Builder(this, "bridge")
                .setContentTitle(getString(R.string.app_name) + " " + AppVersion.label(STATE.apkVersion))
                .setContentText("麦克风桥接运行中")
                .setSmallIcon(android.R.drawable.ic_btn_speak_now)
                .setContentIntent(pi)
                .setOngoing(true)
                .build();
        startForeground(1, notification);
    }
}
