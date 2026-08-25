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
        void onMuteTap();

        void onRotateTap();
    }

    private Listener listener;
    private boolean upsideDown;
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
    private final RectF muteRect = new RectF();
    private final RectF rotateRect = new RectF();
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

    public void setUpsideDown(boolean upsideDown) {
        this.upsideDown = upsideDown;
        invalidate();
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
        boolean live = s.clientConnected && !s.muted && (s.recording || s.playLevel > 0.02f);
        int usbColor = !s.usbConnected ? 0xFFFF5C7A : (s.clientConnected ? 0xFF3DDC97 : 0xFFFFB020);
        accent.setColor(usbColor);
        float usbAlpha = live ? 0.65f + 0.35f * (float) Math.abs(Math.sin(pulse)) : 1f;
        accent.setAlpha((int) (usbAlpha * 255));
        canvas.drawCircle(dp(36), dp(36), dp(8), accent);
        accent.setAlpha(255);

        text.setTextSize(dp(18));
        text.setColor(0xFFE8EEF8);
        canvas.drawText("LX04 PC Bridge", dp(54), dp(42), text);
        String ver = formatVersion(s.apkVersion);

        float rotateW = dp(72);
        float rotateH = dp(32);
        rotateRect.set(w - dp(28) - rotateW, dp(56), w - dp(28), dp(56) + rotateH);
        button.setColor(upsideDown ? 0xFF2A4A3A : 0xFF223154);
        canvas.drawRoundRect(rotateRect, dp(8), dp(8), button);
        text.setTextSize(dp(13));
        String rotateLabel = upsideDown ? "吊装 ✓" : "旋转";
        float rlW = text.measureText(rotateLabel);
        canvas.drawText(rotateLabel, rotateRect.left + (rotateRect.width() - rlW) / 2f,
                rotateRect.top + rotateRect.height() * 0.68f, text);

        text.setTextSize(dp(28));
        text.setColor(0xFF3DDC97);
        float verW = text.measureText(ver);
        canvas.drawText(ver, rotateRect.left - dp(8) - verW, dp(48), text);
        text.setColor(0xFFE8EEF8);
        dim.setTextSize(dp(14));
        canvas.drawText(s.formatLink(), dp(54), dp(64), dim);

        muteRect.set(dp(28), h - dp(70), w - dp(28), h - dp(22));
        if (s.hasPcStats()) {
            drawHardware(canvas, s, w, h);
        } else {
            drawClassic(canvas, s, w, h);
        }

        button.setColor(s.muted ? 0xFF5B2A38 : 0xFF223154);
        canvas.drawRoundRect(muteRect, dp(14), dp(14), button);
        text.setTextSize(dp(20));
        text.setColor(0xFFE8EEF8);
        String muteLabel = s.muted ? "点击取消静音" : "点击静音";
        float tw = text.measureText(muteLabel);
        canvas.drawText(muteLabel, (w - tw) / 2f, muteRect.top + muteRect.height() * 0.68f, text);
    }

    private void drawClassic(Canvas canvas, BridgeState s, int w, int h) {
        text.setTextSize(dp(36));
        text.setColor(0xFFE8EEF8);
        canvas.drawText(s.headline, dp(28), dp(100), text);
        dim.setTextSize(dp(15));
        canvas.drawText(s.detail, dp(28), dp(132), dim);
        playRect.set(dp(28), dp(148), w - dp(28), dp(178));
        drawPlayMeter(canvas, s, w);
    }

    private void drawHardware(Canvas canvas, BridgeState s, int w, int h) {
        dim.setTextSize(dp(13));
        String host = s.pcName.isEmpty() ? "电脑状态" : s.pcName;
        String up = formatUptime(s.pcUptime);
        String line = s.headline + "  ·  " + host + (up.isEmpty() ? "" : "  ·  " + up);
        canvas.drawText(clip(line, rotateRect.left - dp(36)), dp(28), dp(88), dim);

        float gap = dp(8);
        float left = dp(22);
        float right = w - dp(22);
        float top = dp(98);
        float bottom = muteRect.top - dp(36);
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
        String diskSub = !Float.isNaN(s.pcDiskIo)
                ? ("占用  ·  IO " + Math.round(s.pcDiskIo) + "%")
                : "系统盘占用";
        drawStatCard(canvas, left + (cardW + gap) * 3, top, cardW, cardH, "磁盘",
                formatPct(s.pcDisk), diskSub, "", s.pcDisk, Float.NaN);

        dim.setTextSize(dp(13));
        canvas.drawText("↓ " + formatRate(s.pcNetDown) + "   ↑ " + formatRate(s.pcNetUp),
                dp(28), muteRect.top - dp(18), dim);
        playRect.set(dp(220), muteRect.top - dp(32), w - dp(28), muteRect.top - dp(10));
        drawPlayMeter(canvas, s, w);
    }

    private void drawStatCard(Canvas canvas, float x, float y, float cw, float ch,
            String title, String value, String sub, String foot, float usage, float temp) {
        tmpRect.set(x, y, x + cw, y + ch);
        canvas.drawRoundRect(tmpRect, dp(12), dp(12), cardPaint);
        dim.setTextSize(dp(12));
        canvas.drawText(title, x + dp(10), y + dp(16), dim);

        int valueColor = meterColor(usage, temp);
        text.setColor(valueColor);
        text.setTextSize(dp(24));
        canvas.drawText(value, x + dp(10), y + dp(44), text);
        text.setColor(0xFFE8EEF8);

        if (sub != null && !sub.isEmpty()) {
            dim.setTextSize(dp(11));
            canvas.drawText(clip(sub, cw - dp(18)), x + dp(10), y + dp(60), dim);
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
        if (s.muted) {
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
            if (rotateRect.contains(x, y)) {
                if (listener != null) {
                    listener.onRotateTap();
                }
                invalidate();
                return true;
            }
            if (muteRect.contains(x, y)) {
                if (listener != null) {
                    listener.onMuteTap();
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
