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
    private final RectF tmpRect = new RectF();
    private float pulse;

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
        bg.setColor(0xFF0B1220);
        panel.setColor(0xFF141C2E);
        cardPaint.setColor(0xFF1A2438);
        accent.setColor(0xFF3DDC97);
        meterBg.setColor(0xFF1E2A44);
        meter.setColor(0xFF3DDC97);
        button.setColor(0xFF223154);
        text.setColor(0xFFE8EEF8);
        text.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        dim.setColor(0xFF8FA0BE);
        dim.setTypeface(Typeface.create("sans-serif", Typeface.NORMAL));
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        BridgeState s = BridgeService.STATE;
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
        button.setColor(muted ? 0xFF5B2A38 : 0xFF223154);
        canvas.drawRoundRect(rect, dp(12), dp(12), button);
        text.setTextSize(dp(16));
        text.setColor(0xFFE8EEF8);
        float tw = text.measureText(label);
        canvas.drawText(label, rect.centerX() - tw / 2f, rect.top + rect.height() * 0.66f, text);
    }

    private void drawClassic(Canvas canvas, BridgeState s, int w, int h, float muteTop) {
        text.setTextSize(dp(32));
        text.setColor(0xFFE8EEF8);
        canvas.drawText(s.headline, dp(22), dp(72), text);
        dim.setTextSize(dp(15));
        canvas.drawText(s.detail, dp(22), dp(102), dim);
        playRect.set(dp(22), dp(118), w - dp(22), dp(148));
        drawPlayMeter(canvas, s, w);
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
        drawStatCard(canvas, left, top, cardW, cardH, "CPU",
                formatPct(s.pcCpu), formatTemp(s.pcCpuTemp),
                s.pcCores > 0 ? s.pcCores + " 核" : "", s.pcCpu, s.pcCpuTemp);
        drawStatCard(canvas, left + (cardW + gap), top, cardW, cardH, "GPU",
                formatPct(s.pcGpu), gpuSub(s), s.pcGpuName, s.pcGpu, s.pcGpuTemp);
        String ramSub = (s.pcRamTotal > 0)
                ? String.format("%.0f / %.0f GB", s.pcRamUsed, s.pcRamTotal)
                : "";
        drawStatCard(canvas, left + (cardW + gap) * 2, top, cardW, cardH, "内存",
                formatPct(s.pcRam), ramSub, "", s.pcRam, Float.NaN);
        String diskTitle = (s.pcDiskName == null || s.pcDiskName.isEmpty()) ? "磁盘" : s.pcDiskName;
        String diskSub = (s.pcDiskTotal > 0)
                ? String.format("%.0f / %.0f GB", s.pcDiskUsed, s.pcDiskTotal)
                : "占用";
        String diskFoot = !Float.isNaN(s.pcDiskIo)
                ? ("IO " + Math.round(s.pcDiskIo) + "%")
                : "";
        drawStatCard(canvas, left + (cardW + gap) * 3, top, cardW, cardH, diskTitle,
                formatPct(s.pcDisk), diskSub, diskFoot, s.pcDisk, Float.NaN);

        dim.setTextSize(dp(12));
        float meterTop = muteTop - meterH;
        canvas.drawText("↓ " + formatRate(s.pcNetDown) + "  ↑ " + formatRate(s.pcNetUp),
                dp(18), meterTop + dp(14), dim);
        playRect.set(dp(210), meterTop, w - dp(18), muteTop - dp(4));
        drawPlayMeter(canvas, s, w);
    }

    private void drawStatCard(Canvas canvas, float x, float y, float cw, float ch,
            String title, String value, String sub, String foot, float usage, float temp) {
        tmpRect.set(x, y, x + cw, y + ch);
        canvas.drawRoundRect(tmpRect, dp(12), dp(12), cardPaint);
        dim.setTextSize(dp(13));
        canvas.drawText(title, x + dp(10), y + dp(18), dim);

        int valueColor = meterColor(usage, temp);
        text.setColor(valueColor);
        text.setTextSize(dp(28));
        canvas.drawText(value, x + dp(10), y + dp(52), text);
        text.setColor(0xFFE8EEF8);

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
            meter.setColor(0xFF5B6B88);
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
        if (!s.hasPcStats()) {
            dim.setTextSize(dp(13));
            canvas.drawText("扬声器", dp(32), playRect.bottom + dp(16), dim);
            canvas.drawText("帧 " + s.frames + "  丢 " + s.dropped, w - dp(180), playRect.bottom + dp(16), dim);
        }
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

    private static String gpuSub(BridgeState s) {
        StringBuilder b = new StringBuilder();
        if (!Float.isNaN(s.pcGpuTemp)) {
            b.append(Math.round(s.pcGpuTemp)).append("°C");
        }
        if (!Float.isNaN(s.pcGpuWatts) && s.pcGpuWatts >= 1f) {
            if (b.length() > 0) {
                b.append("  ");
            }
            b.append(Math.round(s.pcGpuWatts)).append("W");
        }
        if (!Float.isNaN(s.pcVram)) {
            if (b.length() > 0) {
                b.append("  ");
            }
            b.append("显存 ").append(Math.round(s.pcVram)).append("%");
        }
        return b.toString();
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
