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

        void onHudStyleChanged();
    }

    private Listener listener;
    private final CardEditor editor = new CardEditor(this);
    private final AppMenu menu = new AppMenu(this);
    private final RectF[] cardRects = new RectF[] {
            new RectF(), new RectF(), new RectF(), new RectF()
    };
    private final android.os.Handler touchHandler = new android.os.Handler(android.os.Looper.getMainLooper());
    private int pressSlot = -1;
    private float pressX;
    private float pressY;
    private final Runnable longPress = new Runnable() {
        @Override
        public void run() {
            if (pressSlot >= 0) {
                menu.close();
                editor.open(pressSlot, cardRects[pressSlot]);
                pressSlot = -1;
            }
        }
    };
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
    private boolean wasMirroring;
    private boolean muteRevealTap;
    private long mirrorInteractAt;
    private long muteInteractAt;
    private static final long MUTE_SHOW_MS = 3500;
    private static final long MUTE_FADE_MS = 280;
    private final Runnable hideMirrorBar = new Runnable() {
        @Override
        public void run() {
            invalidate();
            postInvalidateOnAnimation();
        }
    };
    private final Runnable hideMuteBar = new Runnable() {
        @Override
        public void run() {
            invalidate();
            postInvalidateOnAnimation();
        }
    };
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
        ScreenMirror.INSTANCE.attach(this);
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

        if (!s.screenMirror) {
            wasMirroring = false;
        }
        if (s.screenMirror) {
            drawMirror(canvas, s, w, h);
            if (editor.isOpen()) {
                editor.draw(canvas, w, h, lightTheme);
            } else {
                menu.draw(canvas, w, h, lightTheme);
            }
            return;
        }

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

        if (s.hasPcStats()) {
            String host = s.pcName.isEmpty() ? "电脑" : s.pcName;
            String up = formatUptime(s.pcUptime);
            String mid = host + (up.isEmpty() ? "" : "  ·  " + up);
            dim.setTextSize(dp(11));
            canvas.drawText(clip(dim, mid, w - dp(22) - dp(110)), dp(110), dp(27), dim);
        }

        float muteAlpha = muteBarAlpha();
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
                s.micMuted ? "麦克风已静音" : "麦克风", muteAlpha);
        drawMuteButton(canvas, spkMuteRect, s.spkMuted,
                s.spkMuted ? "扬声器已静音" : "扬声器", muteAlpha);
        if (muteAlpha > 0.02f && muteAlpha < 1f) {
            postInvalidateOnAnimation();
        }
        if (editor.isOpen()) {
            editor.draw(canvas, w, h, lightTheme);
        } else {
            menu.draw(canvas, w, h, lightTheme);
        }
    }

    void onHudEdited() {
        if (listener != null) {
            listener.onHudStyleChanged();
        }
    }

    void onMuteAutoHideChanged() {
        if (BridgeService.STATE.autoHideMute) {
            noteMuteInteract();
        } else {
            touchHandler.removeCallbacks(hideMuteBar);
            muteInteractAt = 0;
            invalidate();
        }
    }

    void handleBack() {
        if (editor.isOpen()) {
            editor.close();
            return;
        }
        if (BridgeService.STATE.screenMirror) {
            noteMirrorInteract();
        }
        menu.handleBack();
    }

    private void noteMuteInteract() {
        muteInteractAt = android.os.SystemClock.uptimeMillis();
        touchHandler.removeCallbacks(hideMuteBar);
        if (BridgeService.STATE.autoHideMute) {
            touchHandler.postDelayed(hideMuteBar, MUTE_SHOW_MS);
        }
        invalidate();
    }

    private boolean muteButtonsHidden() {
        return BridgeService.STATE.autoHideMute && muteBarAlpha() < 0.15f;
    }

    private float muteBarAlpha() {
        if (!BridgeService.STATE.autoHideMute) {
            return 1f;
        }
        if (menu.blocksHud() || editor.isOpen()) {
            muteInteractAt = android.os.SystemClock.uptimeMillis();
            touchHandler.removeCallbacks(hideMuteBar);
            touchHandler.postDelayed(hideMuteBar, MUTE_SHOW_MS);
            return 1f;
        }
        if (muteInteractAt == 0) {
            muteInteractAt = android.os.SystemClock.uptimeMillis();
            touchHandler.removeCallbacks(hideMuteBar);
            touchHandler.postDelayed(hideMuteBar, MUTE_SHOW_MS);
            return 1f;
        }
        long idle = android.os.SystemClock.uptimeMillis() - muteInteractAt;
        if (idle < MUTE_SHOW_MS) {
            return 1f;
        }
        float fade = (idle - MUTE_SHOW_MS) / (float) MUTE_FADE_MS;
        if (fade >= 1f) {
            return 0f;
        }
        return 1f - fade;
    }

    private void noteMirrorInteract() {
        mirrorInteractAt = android.os.SystemClock.uptimeMillis();
        touchHandler.removeCallbacks(hideMirrorBar);
        touchHandler.postDelayed(hideMirrorBar, 2800);
        invalidate();
    }

    private float mirrorBarAlpha() {
        if (!wasMirroring) {
            wasMirroring = true;
            mirrorInteractAt = android.os.SystemClock.uptimeMillis();
            touchHandler.removeCallbacks(hideMirrorBar);
            touchHandler.postDelayed(hideMirrorBar, 2800);
        }
        if (menu.blocksHud()) {
            mirrorInteractAt = android.os.SystemClock.uptimeMillis();
            touchHandler.removeCallbacks(hideMirrorBar);
            touchHandler.postDelayed(hideMirrorBar, 2800);
            return 1f;
        }
        long idle = android.os.SystemClock.uptimeMillis() - mirrorInteractAt;
        long showMs = 2800;
        long fadeMs = 320;
        if (idle < showMs) {
            return 1f;
        }
        float fade = (idle - showMs) / (float) fadeMs;
        if (fade >= 1f) {
            return 0f;
        }
        return 1f - fade;
    }

    private void drawMirror(Canvas canvas, BridgeState s, int w, int h) {
        bg.setColor(0xFF000000);
        canvas.drawRect(0, 0, w, h, bg);
        bg.setColor(lightTheme ? 0xFFF3F5F8 : 0xFF0B1220);
        boolean hasFrame = ScreenMirror.INSTANCE.hasFrame();
        if (hasFrame) {
            ScreenMirror.INSTANCE.draw(canvas, w, h);
        }
        float bar = mirrorBarAlpha();
        if (bar > 0.02f) {
            int scrim = Math.max(1, Math.min(255, (int) (0x88 * bar)));
            dim.setColor(scrim << 24);
            canvas.drawRect(0, 0, w, dp(28), dim);
            dim.setColor(colDim);
            int usbColor = !s.usbConnected ? 0xFFFF5C7A : (s.clientConnected ? 0xFF3DDC97 : 0xFFFFB020);
            accent.setColor(usbColor);
            accent.setAlpha(Math.max(1, Math.min(255, (int) (255 * bar))));
            canvas.drawCircle(dp(16), dp(16), dp(6), accent);
            accent.setAlpha(255);

            int textAlpha = Math.max(1, Math.min(255, (int) (255 * bar)));
            text.setTextSize(dp(13));
            text.setColor((textAlpha << 24) | 0x00E8EEF8);
            String title = (s.mirrorTitle == null || s.mirrorTitle.isEmpty()) ? "屏幕镜像" : s.mirrorTitle;
            canvas.drawText(title, dp(30), dp(21), text);
            text.setColor(colText);
        }
        if (bar > 0.02f && bar < 1f) {
            postInvalidateOnAnimation();
        }

        if (!s.clientConnected) {
            drawMirrorMessage(canvas, w, h, "等待上位机", "连接电脑后开始同步画面");
        } else if (!hasFrame) {
            drawMirrorMessage(canvas, w, h, "正在等待电脑画面…", "从右侧滑出菜单可关闭");
        } else if (ScreenMirror.INSTANCE.stale()) {
            drawMirrorMessage(canvas, w, h, "画面中断", "从右侧滑出菜单可关闭");
        }
    }

    private void drawMirrorMessage(Canvas canvas, int w, int h, String headline, String detail) {
        dim.setColor(0xCCFFFFFF);
        dim.setTextSize(dp(18));
        float tw = dim.measureText(headline);
        canvas.drawText(headline, w / 2f - tw / 2f, h / 2f - dp(6), dim);
        dim.setTextSize(dp(13));
        float dw = dim.measureText(detail);
        canvas.drawText(detail, w / 2f - dw / 2f, h / 2f + dp(18), dim);
        dim.setColor(colDim);
    }

    private void drawMuteButton(Canvas canvas, RectF rect, boolean muted, String label, float alpha) {
        if (alpha <= 0.02f) {
            return;
        }
        int a = Math.max(1, Math.min(255, (int) (255 * alpha)));
        button.setColor(muted ? colButtonMute : colButton);
        button.setAlpha(a);
        canvas.drawRoundRect(rect, dp(12), dp(12), button);
        button.setAlpha(255);
        text.setTextSize(dp(16));
        text.setColor((a << 24) | (colText & 0x00FFFFFF));
        float tw = text.measureText(label);
        canvas.drawText(label, rect.centerX() - tw / 2f, rect.top + rect.height() * 0.66f, text);
        text.setColor(colText);
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
            float x = left + (cardW + gap) * i;
            cardRects[i].set(x, top, x + cardW, top + cardH);
            String metric = s.hudStyle.metric(i);
            String subMetric = s.hudStyle.subMetric(i);
            String title = s.hudStyle.title(i, HudStyle.fallbackTitle(metric, s.pcDiskName));
            drawStatCard(canvas, x, top, cardW, cardH, title,
                    formatMetricValue(s, metric), formatMetricValue(s, subMetric),
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
        HudStyle style = BridgeService.STATE.hudStyle;
        float padX = dp(10);
        float innerW = Math.max(dp(24), cw - padX * 2);
        float titleSize = dp(13);
        float valueWant = dp(style.valueSize(slot));
        float subWant = dp(style.subSize(slot));
        boolean hasSub = sub != null && !sub.isEmpty();
        boolean hasFoot = foot != null && !foot.isEmpty();
        float barSpace = dp(16);
        float footSpace = hasFoot ? dp(16) : 0;
        float usableBottom = y + ch - barSpace - footSpace;

        int titleColor = style.titleColor(slot);
        dim.setColor(titleColor != 0 ? titleColor : colDim);
        titleSize = fitText(dim, title, innerW, titleSize, dp(9));
        float titleTop = y + dp(8);
        float titleBase = titleTop - dim.ascent();

        int customValue = style.valueColor(slot);
        int valueColor = customValue != 0 ? customValue : meterColor(usage, temp);
        text.setColor(valueColor);
        valueWant = fitText(text, value, innerW, valueWant, dp(HudStyle.MIN_VALUE_SIZE));
        float afterTitle = titleBase + dim.descent() + dp(4);
        float valueBase = afterTitle - text.ascent();
        float valueBottom = valueBase + text.descent();

        float subBase = 0;
        float subBottom = valueBottom;
        if (hasSub) {
            dim.setColor(colDim);
            subWant = fitText(dim, sub, innerW, subWant, dp(HudStyle.MIN_SUB_SIZE));
            subBase = valueBottom + dp(3) - dim.ascent();
            subBottom = subBase + dim.descent();
        }

        int guard = 0;
        while (subBottom > usableBottom + 1f && guard++ < 48) {
            boolean shrunk = false;
            if (valueWant > dp(HudStyle.MIN_VALUE_SIZE) + 0.5f) {
                valueWant = Math.max(dp(HudStyle.MIN_VALUE_SIZE), valueWant - 1f);
                shrunk = true;
            }
            if (hasSub && subWant > dp(HudStyle.MIN_SUB_SIZE) + 0.5f) {
                subWant = Math.max(dp(HudStyle.MIN_SUB_SIZE), subWant - 1f);
                shrunk = true;
            }
            if (titleSize > dp(9) + 0.5f) {
                titleSize = Math.max(dp(9), titleSize - 1f);
                shrunk = true;
            }
            if (!shrunk) {
                break;
            }
            dim.setTextSize(titleSize);
            titleBase = titleTop - dim.ascent();
            afterTitle = titleBase + dim.descent() + dp(4);
            text.setTextSize(valueWant);
            valueBase = afterTitle - text.ascent();
            valueBottom = valueBase + text.descent();
            if (hasSub) {
                dim.setTextSize(subWant);
                subBase = valueBottom + dp(3) - dim.ascent();
                subBottom = subBase + dim.descent();
            } else {
                subBottom = valueBottom;
            }
        }

        canvas.save();
        tmpRect.inset(1, 1);
        canvas.clipRect(tmpRect);
        tmpRect.set(x, y, x + cw, y + ch);
        dim.setColor(titleColor != 0 ? titleColor : colDim);
        dim.setTextSize(titleSize);
        canvas.drawText(clip(dim, title, innerW), x + padX, titleBase, dim);
        text.setColor(valueColor);
        text.setTextSize(valueWant);
        canvas.drawText(clip(text, value, innerW), x + padX, valueBase, text);
        text.setColor(colText);
        if (hasSub) {
            dim.setColor(colDim);
            dim.setTextSize(subWant);
            canvas.drawText(clip(dim, sub, innerW), x + padX, subBase, dim);
        }
        if (hasFoot) {
            dim.setTextSize(dp(11));
            canvas.drawText(clip(dim, foot, innerW), x + padX, y + ch - barSpace - dp(2), dim);
        }
        canvas.restore();
        dim.setColor(colDim);

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
    public void computeScroll() {
        super.computeScroll();
        boolean more = false;
        if (editor.advance()) {
            more = true;
        }
        if (!editor.isOpen() && menu.advance()) {
            more = true;
        }
        if (more) {
            postInvalidateOnAnimation();
        }
    }

    @Override
    public boolean onTouchEvent(MotionEvent event) {
        if (editor.isOpen()) {
            return editor.onTouch(event);
        }
        float x = event.getX();
        float y = event.getY();
        int action = event.getActionMasked();
        int w = getWidth();
        if (action == MotionEvent.ACTION_DOWN) {
            if (BridgeService.STATE.screenMirror) {
                noteMirrorInteract();
            } else if (BridgeService.STATE.autoHideMute) {
                muteRevealTap = muteButtonsHidden();
                noteMuteInteract();
            }
            menu.onDown(x, y, w, event);
            if (menu.blocksHud()) {
                return true;
            }
            pressSlot = cardIndexAt(x, y);
            pressX = x;
            pressY = y;
            if (pressSlot >= 0) {
                touchHandler.postDelayed(longPress, 450);
            }
            return true;
        }
        if (action == MotionEvent.ACTION_MOVE) {
            if (menu.onMove(x, y, w, event)) {
                touchHandler.removeCallbacks(longPress);
                pressSlot = -1;
                return true;
            }
            if (menu.blocksHud()) {
                return true;
            }
            if (pressSlot >= 0 && (Math.abs(x - pressX) > dp(12) || Math.abs(y - pressY) > dp(12))) {
                touchHandler.removeCallbacks(longPress);
                pressSlot = -1;
            }
            return true;
        }
        if (action == MotionEvent.ACTION_CANCEL) {
            muteRevealTap = false;
            menu.onCancel();
            touchHandler.removeCallbacks(longPress);
            pressSlot = -1;
            return true;
        }
        if (action == MotionEvent.ACTION_UP) {
            touchHandler.removeCallbacks(longPress);
            pressSlot = -1;
            if (menu.onUp(x, y, w, event)) {
                muteRevealTap = false;
                return true;
            }
            if (menu.blocksHud()) {
                return true;
            }
            if (BridgeService.STATE.screenMirror) {
                return true;
            }
            if (muteRevealTap) {
                muteRevealTap = false;
                return true;
            }
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
            return true;
        }
        return super.onTouchEvent(event);
    }

    private int cardIndexAt(float x, float y) {
        if (BridgeService.STATE.screenMirror || !BridgeService.STATE.hasPcStats()) {
            return -1;
        }
        for (int i = 0; i < cardRects.length; i++) {
            if (cardRects[i].contains(x, y)) {
                return i;
            }
        }
        return -1;
    }

    private static String formatMetricValue(BridgeState s, String metric) {
        if (metric == null || metric.isEmpty() || "none".equals(metric)) {
            return "";
        }
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
        if ("ramGB".equals(metric)) {
            if (s.pcRamTotal <= 0) {
                return "--";
            }
            return String.format("%.0f / %.0f GB", s.pcRamUsed, s.pcRamTotal);
        }
        if ("diskGB".equals(metric)) {
            if (s.pcDiskTotal <= 0) {
                return "--";
            }
            return String.format("%.0f / %.0f GB", s.pcDiskUsed, s.pcDiskTotal);
        }
        if ("cores".equals(metric)) {
            return s.pcCores > 0 ? s.pcCores + " 核" : "--";
        }
        if ("gpuN".equals(metric)) {
            return s.pcGpuName != null && !s.pcGpuName.isEmpty() ? s.pcGpuName : "--";
        }
        return formatPct(metricUsage(s, metric));
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
        if ("ram".equals(metric) || "ramGB".equals(metric)) {
            return s.pcRam;
        }
        if ("disk".equals(metric) || "diskGB".equals(metric)) {
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

    private String clip(Paint paint, String value, float maxWidth) {
        if (value == null || value.isEmpty()) {
            return "";
        }
        if (paint.measureText(value) <= maxWidth) {
            return value;
        }
        String ellip = "…";
        for (int i = value.length() - 1; i > 0; i--) {
            String cut = value.substring(0, i) + ellip;
            if (paint.measureText(cut) <= maxWidth) {
                return cut;
            }
        }
        return ellip;
    }

    private static float fitText(Paint paint, String value, float maxWidth, float want, float min) {
        if (value == null || value.isEmpty()) {
            return want;
        }
        float size = want;
        paint.setTextSize(size);
        while (size > min && paint.measureText(value) > maxWidth) {
            size -= 1f;
            paint.setTextSize(size);
        }
        return size;
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

    float dp(float v) {
        return v * getResources().getDisplayMetrics().density;
    }
}
