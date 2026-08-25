package com.lx04.pcbridge;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.util.AttributeSet;
import android.view.MotionEvent;
import android.view.View;

public class StatusHudView extends View {
    public interface Listener {
        void onMicMuteTap();

        void onSpkMuteTap();

        void onResetStyleTap();
    }

    private Listener listener;
    private final Paint bg = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint panel = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint cardPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint accent = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint text = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint dim = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint meterBg = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint meter = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint button = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final RectF playRect = new RectF();
    private final RectF micMuteRect = new RectF();
    private final RectF spkMuteRect = new RectF();
    private final RectF resetRect = new RectF();
    private final RectF tmpRect = new RectF();
    private float pulse;
    private boolean lightTheme;
    private int colText;
    private int colDim;
    private int colButton;
    private int colButtonMute;
    private int colPlayMute;

    static int windowColor(boolean light) {
        return light ? 0xFFF3F5F8 : 0xFF0B1220;
    }

    public StatusHudView(Context context) {
        super(context);
        init();
    }

    public StatusHudView(Context context, AttributeSet attrs) {
        super(context, attrs);
        init();
    }

    public void setListener(Listener listener) {
        this.listener = listener;
    }

    private void init() {
        setClickable(true);
        text.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        dim.setTypeface(Typeface.create("sans-serif", Typeface.NORMAL));
        applyPalette(false);
    }

    private void applyPalette(boolean light) {
        lightTheme = light;
        if (light) {
            bg.setColor(0xFFF3F5F8);
            panel.setColor(0xFFFFFFFF);
            cardPaint.setColor(0xFFE8EEF5);
            meterBg.setColor(0xFFD5DDE8);
            colButton = 0xFFD3DCE8;
            colButtonMute = 0xFFE9C9CF;
            colText = 0xFF1A2438;
            colDim = 0xFF5A6B84;
            dim.setColor(colDim);
            colPlayMute = 0xFF9AABC0;
        } else {
            bg.setColor(0xFF0B1220);
            panel.setColor(0xFF141C2E);
            cardPaint.setColor(0xFF1A2438);
            meterBg.setColor(0xFF1E2A44);
            colButton = 0xFF223154;
            colButtonMute = 0xFF5B2A38;
            colText = 0xFFE8EEF8;
            colDim = 0xFF8FA0BE;
            dim.setColor(colDim);
            colPlayMute = 0xFF5B6B88;
        }
        button.setColor(colButton);
        text.setColor(colText);
        meter.setColor(0xFF3DDC97);
        accent.setColor(0xFF3DDC97);
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        BridgeState s = BridgeService.STATE;
        if (s.lightTheme != lightTheme) {
            applyPalette(s.lightTheme);
        }
        int w = getWidth();
        int h = getHeight();
        canvas.drawRect(0, 0, w, h, bg);

        float p = dp(12);
        RectF card = new RectF(p, p, w - p, h - p);
        canvas.drawRoundRect(card, dp(18), dp(18), panel);

        pulse = (pulse + 0.08f) % ((float) (Math.PI * 2));
        boolean live = s.clientConnected && (
                (s.recording && !s.micMuted) || (s.playLevel > 0.02f && !s.spkMuted));
        int usbColor = !s.usbConnected ? 0xFFFF5C7A : (s.clientConnected ? 0xFF3DDC97 : 0xFFFFB020);
        accent.setColor(usbColor);
        float usbAlpha = live ? 0.65f + 0.35f * (float) Math.abs(Math.sin(pulse)) : 1f;
        accent.setAlpha((int) (usbAlpha * 255));
        canvas.drawCircle(dp(22), dp(22), dp(7), accent);
        accent.setAlpha(255);

        dim.setTextSize(dp(12));
        canvas.drawText(s.formatLink(), dp(36), dp(27), dim);

        dim.setTextSize(dp(11));
        String ver = formatVersion(s.apkVersion);
        float verW = dim.measureText(ver);
        canvas.drawText(ver, w - dp(22) - verW, dp(27), dim);

        if (s.hasPcStats()) {
            String host = s.pcName.isEmpty() ? "电脑" : s.pcName;
            String up = formatUptime(s.pcUptime);
            String mid = host + (up.isEmpty() ? "" : "  ·  " + up);
            canvas.drawText(clip(mid, w - dp(80) - verW - dp(110)), dp(110), dp(27), dim);
        }

        float muteTop = h - dp(64);
        float muteGap = dp(10);
        micMuteRect.set(dp(18), muteTop, w / 2f - muteGap / 2f, h - dp(12));
        spkMuteRect.set(w / 2f + muteGap / 2f, muteTop, w - dp(18), h - dp(12));
        resetRect.setEmpty();
        if (s.hasPcStats()) {
            drawHardware(canvas, s, w, h, muteTop);
        } else {
            drawClassic(canvas, s, w, h, muteTop);
        }

        drawMuteButton(canvas, micMuteRect, s.micMuted,
                s.micMuted ? "麦克风已静音" : "麦克风");
        drawMuteButton(canvas, spkMuteRect, s.spkMuted,
                s.spkMuted ? "扬声器已静音" : "扬声器");
    }

    private void drawMuteButton(Canvas canvas, RectF rect, boolean muted, String label) {
        button.setColor(muted ? colButtonMute : colButton);
        canvas.drawRoundRect(rect, dp(12), dp(12), button);
        text.setTextSize(dp(16));
        text.setColor(colText);
        float tw = text.measureText(label);
        canvas.drawText(label, rect.centerX() - tw / 2f, rect.top + rect.height() * 0.66f, text);
    }

    private void drawClassic(Canvas canvas, BridgeState s, int w, int h, float muteTop) {
        text.setTextSize(dp(32));
        text.setColor(colText);
        canvas.drawText(s.headline, dp(22), dp(72), text);
        dim.setTextSize(dp(15));
        canvas.drawText(s.detail, dp(22), dp(102), dim);
        playRect.set(dp(22), dp(118), w - dp(22), dp(148));
        drawPlayMeter(canvas, s, w);
        if (!s.clientConnected) {
            drawResetButton(canvas, w, muteTop);
        }
    }

    private void drawHardware(Canvas canvas, BridgeState s, int w, int h, float muteTop) {
        float gap = dp(8);
        float left = dp(16);
        float right = w - dp(16);
        float top = dp(44);
        float meterH = dp(18);
        float bottom = muteTop - dp(8) - meterH;
        float cardH = bottom - top;
        float cardW = (right - left - gap * 3) / 4f;
        for (int i = 0; i < 4; i++) {
            String metric = s.hudStyle.metric(i);
            String title = s.hudStyle.title(i, HudStyle.fallbackTitle(metric, s.pcDiskName));
            drawStatCard(canvas, left + (cardW + gap) * i, top, cardW, cardH, title,
                    formatMetricValue(s, metric), formatMetricSub(s, metric),
                    formatMetricFoot(s, metric), metricUsage(s, metric), metricTemp(s, metric), i);
        }

        dim.setTextSize(dp(12));
        float meterTop = muteTop - meterH;
        canvas.drawText("↓ " + formatRate(s.pcNetDown) + "  ↑ " + formatRate(s.pcNetUp),
                dp(18), meterTop + dp(14), dim);
        playRect.set(dp(210), meterTop, w - dp(18), muteTop - dp(4));
        drawPlayMeter(canvas, s, w);
    }

    private void drawStatCard(Canvas canvas, float x, float y, float cw, float ch,
            String title, String value, String sub, String foot, float usage, float temp, int slot) {
        tmpRect.set(x, y, x + cw, y + ch);
        canvas.drawRoundRect(tmpRect, dp(12), dp(12), cardPaint);
        int titleColor = BridgeService.STATE.hudStyle.titleColor(slot);
        dim.setColor(titleColor != 0 ? titleColor : colDim);
        dim.setTextSize(dp(13));
        canvas.drawText(title, x + dp(10), y + dp(18), dim);
        dim.setColor(colDim);

        int customValue = BridgeService.STATE.hudStyle.valueColor(slot);
        int valueColor = customValue != 0 ? customValue : meterColor(usage, temp);
        text.setColor(valueColor);
        text.setTextSize(dp(28));
        canvas.drawText(value, x + dp(10), y + dp(52), text);
        text.setColor(colText);

        if (sub != null && !sub.isEmpty()) {
            dim.setTextSize(dp(11));
            canvas.drawText(clip(sub, cw - dp(18)), x + dp(10), y + dp(72), dim);
        }
        if (foot != null && !foot.isEmpty()) {
            dim.setTextSize(dp(11));
            canvas.drawText(clip(foot, cw - dp(18)), x + dp(10), y + ch - dp(22), dim);
        }

        float barTop = y + ch - dp(14);
        tmpRect.set(x + dp(10), barTop, x + cw - dp(10), barTop + dp(7));
        canvas.drawRoundRect(tmpRect, dp(4), dp(4), meterBg);
        float fill = Float.isNaN(usage) ? 0.04f : Math.max(0.04f, Math.min(1f, usage / 100f));
        meter.setColor(valueColor);
        tmpRect.right = tmpRect.left + Math.max(dp(6), (cw - dp(20)) * fill);
        canvas.drawRoundRect(tmpRect, dp(4), dp(4), meter);
    }

    private void drawPlayMeter(Canvas canvas, BridgeState s, int w) {
        canvas.drawRoundRect(playRect, dp(10), dp(10), meterBg);
        float play = Math.max(0f, Math.min(1f, s.playLevel * 2.4f));
        if (s.spkMuted) {
            meter.setColor(colPlayMute);
            play = 0.04f;
        } else if (play > 0.85f) {
            meter.setColor(0xFFFF5C7A);
        } else if (play > 0.55f) {
            meter.setColor(0xFFFFB020);
        } else {
            meter.setColor(0xFF6EA8FF);
        }
        RectF playFill = new RectF(playRect.left + 4, playRect.top + 4,
                playRect.left + 4 + Math.max(dp(8), (playRect.width() - 8) * Math.max(0.04f, play)),
                playRect.bottom - 4);
        canvas.drawRoundRect(playFill, dp(8), dp(8), meter);
        if (!s.hasPcStats() && s.clientConnected) {
            dim.setTextSize(dp(13));
            canvas.drawText("扬声器", dp(32), playRect.bottom + dp(16), dim);
            canvas.drawText("帧 " + s.frames + "  丢 " + s.dropped, w - dp(180), playRect.bottom + dp(16), dim);
        }
    }

    private void drawResetButton(Canvas canvas, int w, float muteTop) {
        text.setTextSize(dp(16));
        text.setColor(colText);
        String label = "重置样式";
        float tw = text.measureText(label);
        float bw = tw + dp(48);
        float bh = dp(40);
        float top = playRect.bottom + dp(36);
        if (top + bh > muteTop - dp(8)) {
            top = muteTop - dp(8) - bh;
        }
        resetRect.set(w / 2f - bw / 2f, top, w / 2f + bw / 2f, top + bh);
        button.setColor(colButton);
        canvas.drawRoundRect(resetRect, dp(12), dp(12), button);
        canvas.drawText(label, resetRect.centerX() - tw / 2f, resetRect.top + resetRect.height() * 0.66f, text);
    }

    @Override
    public boolean onTouchEvent(MotionEvent event) {
        if (event.getAction() == MotionEvent.ACTION_UP) {
            float x = event.getX();
            float y = event.getY();
            if (micMuteRect.contains(x, y)) {
                if (listener != null) {
                    listener.onMicMuteTap();
                }
                invalidate();
                return true;
            }
            if (spkMuteRect.contains(x, y)) {
                if (listener != null) {
                    listener.onSpkMuteTap();
                }
                invalidate();
                return true;
            }
            if (!resetRect.isEmpty() && resetRect.contains(x, y)) {
                if (listener != null) {
                    listener.onResetStyleTap();
                }
                invalidate();
                return true;
            }
        }
        return super.onTouchEvent(event);
    }

    private static String formatVersion(String apkVersion) {
        if (apkVersion == null || apkVersion.isEmpty()) {
            return "v?";
        }
        return apkVersion.startsWith("v") || apkVersion.startsWith("V")
                ? apkVersion
                : "v" + apkVersion;
    }

    private static String formatMetricValue(BridgeState s, String metric) {
        if ("cpuT".equals(metric)) {
            return formatTemp(s.pcCpuTemp);
        }
        if ("gpuT".equals(metric)) {
            return formatTemp(s.pcGpuTemp);
        }
        if ("gpuW".equals(metric)) {
            if (Float.isNaN(s.pcGpuWatts) || s.pcGpuWatts < 1f) {
                return "--";
            }
            return Math.round(s.pcGpuWatts) + "W";
        }
        if ("netD".equals(metric)) {
            return formatRate(s.pcNetDown);
        }
        if ("netU".equals(metric)) {
            return formatRate(s.pcNetUp);
        }
        return formatPct(metricUsage(s, metric));
    }

    private static String formatMetricSub(BridgeState s, String metric) {
        if ("cpu".equals(metric)) {
            return formatTemp(s.pcCpuTemp);
        }
        if ("cpuT".equals(metric)) {
            return s.pcCores > 0 ? s.pcCores + " 核" : "";
        }
        if ("gpu".equals(metric) || "gpuT".equals(metric) || "gpuW".equals(metric)
                || "gpuFan".equals(metric) || "vram".equals(metric)) {
            return gpuSub(s, metric);
        }
        if ("ram".equals(metric) && s.pcRamTotal > 0) {
            return String.format("%.0f / %.0f GB", s.pcRamUsed, s.pcRamTotal);
        }
        if (("disk".equals(metric) || "diskIo".equals(metric)) && s.pcDiskTotal > 0) {
            return String.format("%.0f / %.0f GB", s.pcDiskUsed, s.pcDiskTotal);
        }
        return "";
    }

    private static String formatMetricFoot(BridgeState s, String metric) {
        if ("disk".equals(metric) && !Float.isNaN(s.pcDiskIo)) {
            return "IO " + Math.round(s.pcDiskIo) + "%";
        }
        if ("gpu".equals(metric) && s.pcGpuName != null && !s.pcGpuName.isEmpty()) {
            return s.pcGpuName;
        }
        return "";
    }

    private static float metricUsage(BridgeState s, String metric) {
        if ("cpu".equals(metric)) {
            return s.pcCpu;
        }
        if ("gpu".equals(metric)) {
            return s.pcGpu;
        }
        if ("gpuFan".equals(metric)) {
            return s.pcGpuFan;
        }
        if ("vram".equals(metric)) {
            return s.pcVram;
        }
        if ("ram".equals(metric)) {
            return s.pcRam;
        }
        if ("disk".equals(metric)) {
            return s.pcDisk;
        }
        if ("diskIo".equals(metric)) {
            return s.pcDiskIo;
        }
        if ("cpuT".equals(metric)) {
            return s.pcCpuTemp;
        }
        if ("gpuT".equals(metric)) {
            return s.pcGpuTemp;
        }
        if ("gpuW".equals(metric)) {
            return Float.isNaN(s.pcGpuWatts) ? Float.NaN : Math.min(100f, s.pcGpuWatts / 4.5f);
        }
        if ("netD".equals(metric)) {
            return Math.min(100f, s.pcNetDown / 50000f);
        }
        if ("netU".equals(metric)) {
            return Math.min(100f, s.pcNetUp / 50000f);
        }
        return Float.NaN;
    }

    private static float metricTemp(BridgeState s, String metric) {
        if ("cpu".equals(metric) || "cpuT".equals(metric)) {
            return s.pcCpuTemp;
        }
        if ("gpu".equals(metric) || "gpuT".equals(metric) || "gpuW".equals(metric)
                || "gpuFan".equals(metric) || "vram".equals(metric)) {
            return s.pcGpuTemp;
        }
        return Float.NaN;
    }

    private static String gpuSub(BridgeState s, String skip) {
        StringBuilder b = new StringBuilder();
        if (!"gpuT".equals(skip) && !Float.isNaN(s.pcGpuTemp)) {
            b.append(Math.round(s.pcGpuTemp)).append("°C");
        }
        if (!"gpuW".equals(skip) && !Float.isNaN(s.pcGpuWatts) && s.pcGpuWatts >= 1f) {
            if (b.length() > 0) {
                b.append("  ");
            }
            b.append(Math.round(s.pcGpuWatts)).append("W");
        }
        if (!"vram".equals(skip) && !Float.isNaN(s.pcVram)) {
            if (b.length() > 0) {
                b.append("  ");
            }
            b.append("显存 ").append(Math.round(s.pcVram)).append("%");
        }
        if (!"gpu".equals(skip) && !Float.isNaN(s.pcGpu)) {
            if (b.length() > 0) {
                b.append("  ");
            }
            b.append(Math.round(s.pcGpu)).append("%");
        }
        return b.toString();
    }

    private static String formatPct(float value) {
        if (Float.isNaN(value)) {
            return "--";
        }
        return Math.round(value) + "%";
    }

    private static String formatTemp(float temp) {
        if (Float.isNaN(temp)) {
            return "--";
        }
        return Math.round(temp) + "°C";
    }

    private static String formatRate(float bytesPerSec) {
        if (bytesPerSec < 1024f) {
            return Math.round(bytesPerSec) + " B/s";
        }
        if (bytesPerSec < 1024f * 1024f) {
            return String.format("%.1f KB/s", bytesPerSec / 1024f);
        }
        return String.format("%.2f MB/s", bytesPerSec / (1024f * 1024f));
    }

    private static String formatUptime(long seconds) {
        if (seconds <= 0) {
            return "";
        }
        long h = seconds / 3600;
        long m = (seconds % 3600) / 60;
        if (h >= 24) {
            long d = h / 24;
            return "开机 " + d + "天" + (h % 24) + "小时";
        }
        return "开机 " + h + "小时" + m + "分";
    }

    private String clip(String value, float maxWidth) {
        if (value == null || value.isEmpty()) {
            return "";
        }
        if (dim.measureText(value) <= maxWidth) {
            return value;
        }
        String ellip = "…";
        for (int i = value.length() - 1; i > 0; i--) {
            String cut = value.substring(0, i) + ellip;
            if (dim.measureText(cut) <= maxWidth) {
                return cut;
            }
        }
        return ellip;
    }

    private static int meterColor(float usage, float temp) {
        float heat = Float.isNaN(temp) ? 0f : temp;
        float load = Float.isNaN(usage) ? 0f : usage;
        if (heat >= 85f || load >= 90f) {
            return 0xFFFF5C7A;
        }
        if (heat >= 70f || load >= 70f) {
            return 0xFFFFB020;
        }
        return 0xFF3DDC97;
    }

    private float dp(float v) {
        return v * getResources().getDisplayMetrics().density;
    }
}
