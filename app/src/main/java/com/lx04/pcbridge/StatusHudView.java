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
    private final Paint accent = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint text = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint dim = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint meterBg = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint meter = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint button = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final RectF playRect = new RectF();
    private final RectF muteRect = new RectF();
    private final RectF rotateRect = new RectF();
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

        text.setTextSize(dp(36));
        canvas.drawText(s.headline, dp(28), dp(100), text);
        dim.setTextSize(dp(15));
        canvas.drawText(s.detail, dp(28), dp(132), dim);

        playRect.set(dp(28), dp(148), w - dp(28), dp(178));
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

        dim.setTextSize(dp(13));
        canvas.drawText("扬声器", dp(32), dp(192), dim);
        canvas.drawText("帧 " + s.frames + "  丢 " + s.dropped, w - dp(180), dp(192), dim);

        muteRect.set(dp(28), h - dp(78), w - dp(28), h - dp(28));
        button.setColor(s.muted ? 0xFF5B2A38 : 0xFF223154);
        canvas.drawRoundRect(muteRect, dp(14), dp(14), button);
        text.setTextSize(dp(20));
        String muteLabel = s.muted ? "点击取消静音" : "点击静音";
        float tw = text.measureText(muteLabel);
        canvas.drawText(muteLabel, (w - tw) / 2f, h - dp(46), text);
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

    private float dp(float v) {
        return v * getResources().getDisplayMetrics().density;
    }
}
