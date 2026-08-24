package com.lx04.pcbridge;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.os.IBinder;
import android.os.PowerManager;
import android.os.SystemClock;

import org.json.JSONObject;

public class BridgeService extends Service {
    public static final BridgeState STATE = new BridgeState();

    private AudioCapture capture;
    private TcpBridgeServer server;
    private UsbMonitor usbMonitor;
    private PowerManager.WakeLock wakeLock;
    private long lastAudioMs;

    @Override
    public void onCreate() {
        super.onCreate();
        STATE.androidRelease = android.os.Build.VERSION.RELEASE;
        startAsForeground();
        PowerManager pm = (PowerManager) getSystemService(POWER_SERVICE);
        if (pm != null) {
            wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "lx04:bridge");
            wakeLock.setReferenceCounted(false);
            wakeLock.acquire();
        }
        capture = new AudioCapture(this::onAudio);
        server = new TcpBridgeServer(STATE, new TcpBridgeServer.Callbacks() {
            @Override
            public void prepareForClient() {
                startMic();
            }

            @Override
            public void onClient(boolean connected, String helloAckName) {
                STATE.clientConnected = connected;
                STATE.pcName = helloAckName == null ? "" : helloAckName;
                if (connected) {
                    refreshHeadline();
                } else {
                    stopMic();
                    refreshHeadline();
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
                } else if ("mute".equals(cmd)) {
                    STATE.muted = true;
                } else if ("unmute".equals(cmd)) {
                    STATE.muted = false;
                } else if ("toggle_mute".equals(cmd)) {
                    STATE.muted = !STATE.muted;
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
        refreshHeadline();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && "toggle_mute".equals(intent.getAction())) {
            STATE.muted = !STATE.muted;
            refreshHeadline();
        }
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        if (usbMonitor != null) {
            usbMonitor.stop();
        }
        if (server != null) {
            server.stop();
        }
        stopMic();
        if (wakeLock != null && wakeLock.isHeld()) {
            wakeLock.release();
        }
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    public static void toggleMute() {
        STATE.muted = !STATE.muted;
        if (STATE.clientConnected) {
            STATE.headline = STATE.muted ? "已静音" : "正在拾音";
        }
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
        if (STATE.muted) {
            java.util.Arrays.fill(pcm, 0, length, (byte) 0);
            STATE.level = 0f;
        }
        if (server != null) {
            server.sendAudio(pcm, length, STATE.muted);
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
        if (STATE.muted) {
            STATE.headline = "已静音";
        } else if (STATE.recording) {
            STATE.headline = "正在拾音";
        } else {
            STATE.headline = "已连接电脑";
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
                    "bridge", "LX04 Bridge", NotificationManager.IMPORTANCE_LOW);
            channel.setShowBadge(false);
            nm.createNotificationChannel(channel);
        }
        Intent launch = new Intent(this, MainActivity.class);
        PendingIntent pi = PendingIntent.getActivity(this, 0, launch,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification notification = new Notification.Builder(this, "bridge")
                .setContentTitle(getString(R.string.app_name))
                .setContentText("麦克风桥接运行中")
                .setSmallIcon(android.R.drawable.ic_btn_speak_now)
                .setContentIntent(pi)
                .setOngoing(true)
                .build();
        startForeground(1, notification);
    }
}
