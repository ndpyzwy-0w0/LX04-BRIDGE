package com.lx04.pcbridge;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Path;
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

        void onPointer(float x, float y, String act);

        void onToastAction(String id, String label);

        void onToastDismiss();
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
    private final Paint sparkStroke = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint sparkFill = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Path sparkPath = new Path();
    private final Path sparkFillPath = new Path();
    private final float[] sparkBuf = new float[SparkHistory.LEN];
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
    private boolean pointerDown;
    private final RectF toastCard = new RectF();
    private final RectF[] toastBtnRects = new RectF[] {
            new RectF(), new RectF(), new RectF(), new RectF(), new RectF()
    };
    private int toastBtnCount;
    private int toastPressBtn = -1;
    private boolean toastPressOutside;
    private long mirrorInteractAt;
    private long muteInteractAt;
    private long lastMuteAnimMs;
    private float muteChrome = 1f;
    private static final long MUTE_SHOW_MS = 3500;
    private static final long MUTE_FADE_MS = 320;
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
        sparkStroke.setStyle(Paint.Style.STROKE);
        sparkStroke.setStrokeCap(Paint.Cap.ROUND);
        sparkStroke.setStrokeJoin(Paint.Join.ROUND);
        sparkFill.setStyle(Paint.Style.FILL);
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

        if (!s.screenMirror && !s.toastOverlay) {
            wasMirroring = false;
        }
        if (s.screenMirror || s.toastOverlay) {
            drawMirror(canvas, s, w, h);
            if (editor.isOpen()) {
                editor.draw(canvas, w, h, lightTheme);
            } else {
                menu.draw(canvas, w, h, lightTheme);
            }
            return;
        }

        boolean customBg = HudBackground.INSTANCE.hasImage();
        HudBackground.INSTANCE.draw(canvas, w, h);
        int hudAlpha = HudBackground.INSTANCE.alpha255();
        boolean faded = hudAlpha < 255;
        if (faded) {
            canvas.saveLayerAlpha(0, 0, w, h, hudAlpha);
        }

        if (!customBg) {
            float p = dp(12);
            RectF card = new RectF(p, p, w - p, h - p);
            canvas.drawRoundRect(card, dp(18), dp(18), panel);
        }

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

        float clockLeft = drawClock(canvas, w, dp(27), colText, dp(13));

        if (s.hasPcStats()) {
            String host = s.pcName.isEmpty() ? "电脑" : s.pcName;
            String up = formatUptime(s.pcUptime);
            String mid = host + (up.isEmpty() ? "" : "  ·  " + up);
            dim.setTextSize(dp(11));
            canvas.drawText(clip(dim, mid, Math.max(0f, clockLeft - dp(12) - dp(110))),
                    dp(110), dp(27), dim);
        }

        float mutePad = dp(12);
        float muteBar = dp(52);
        float shown = ease(muteChrome);
        float shownTop = h - mutePad - muteBar;
        float hiddenTop = h - mutePad;
        float muteTop = hiddenTop + (shownTop - hiddenTop) * shown;
        float slide = (1f - shown) * muteBar;
        float muteGap = dp(10);
        micMuteRect.set(dp(18), shownTop + slide, w / 2f - muteGap / 2f, h - mutePad + slide);
        spkMuteRect.set(w / 2f + muteGap / 2f, shownTop + slide, w - dp(18), h - mutePad + slide);
        resetRect.setEmpty();
        if (s.hasPcStats()) {
            drawHardware(canvas, s, w, h, muteTop);
        } else {
            drawClassic(canvas, s, w, h, muteTop);
        }

        drawMuteButton(canvas, micMuteRect, s.micMuted,
                s.micMuted ? "麦克风已静音" : "麦克风", shown);
        drawMuteButton(canvas, spkMuteRect, s.spkMuted,
                s.spkMuted ? "扬声器已静音" : "扬声器", shown);
        if (shown > 0.02f && shown < 1f) {
            postInvalidateOnAnimation();
        }
        if (faded) {
            canvas.restore();
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
        lastMuteAnimMs = 0;
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
        if (BridgeService.STATE.screenMirror || BridgeService.STATE.toastOverlay) {
            noteMirrorInteract();
        }
        menu.handleBack();
    }

    private void noteMuteInteract() {
        muteInteractAt = android.os.SystemClock.uptimeMillis();
        lastMuteAnimMs = 0;
        touchHandler.removeCallbacks(hideMuteBar);
        if (BridgeService.STATE.autoHideMute) {
            touchHandler.postDelayed(hideMuteBar, MUTE_SHOW_MS);
        }
        invalidate();
        postInvalidateOnAnimation();
    }

    private boolean muteButtonsHidden() {
        return BridgeService.STATE.autoHideMute && muteChrome < 0.15f;
    }

    private float desiredMuteChrome() {
        if (!BridgeService.STATE.autoHideMute) {
            return 1f;
        }
        long now = android.os.SystemClock.uptimeMillis();
        if (menu.blocksHud() || editor.isOpen()) {
            muteInteractAt = now;
            touchHandler.removeCallbacks(hideMuteBar);
            touchHandler.postDelayed(hideMuteBar, MUTE_SHOW_MS);
            return 1f;
        }
        if (muteInteractAt == 0) {
            muteInteractAt = now;
            touchHandler.removeCallbacks(hideMuteBar);
            touchHandler.postDelayed(hideMuteBar, MUTE_SHOW_MS);
            return 1f;
        }
        return now - muteInteractAt < MUTE_SHOW_MS ? 1f : 0f;
    }

    private boolean advanceMuteChrome() {
        float target = desiredMuteChrome();
        long now = android.os.SystemClock.uptimeMillis();
        float dt = lastMuteAnimMs == 0 ? 0f : Math.min(0.05f, (now - lastMuteAnimMs) / 1000f);
        lastMuteAnimMs = now;
        float diff = target - muteChrome;
        if (Math.abs(diff) < 0.012f) {
            muteChrome = target;
            return false;
        }
        float step = (1000f / MUTE_FADE_MS) * Math.max(dt, 1f / 120f);
        muteChrome += Math.signum(diff) * Math.min(Math.abs(diff), step);
        if (muteChrome < 0f) {
            muteChrome = 0f;
        } else if (muteChrome > 1f) {
            muteChrome = 1f;
        }
        return muteChrome != target;
    }

    private static float ease(float t) {
        if (t <= 0f) {
            return 0f;
        }
        if (t >= 1f) {
            return 1f;
        }
        return t * t * (3f - 2f * t);
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
        if (s.toastOverlay) {
            drawToast(canvas, s, w, h);
            return;
        }
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
            int barText = (textAlpha << 24) | 0x00E8EEF8;
            String title;
            if (s.toastOverlay) {
                title = (s.toastTitle == null || s.toastTitle.isEmpty()) ? "系统弹窗" : s.toastTitle;
            } else {
                title = (s.mirrorTitle == null || s.mirrorTitle.isEmpty()) ? "屏幕镜像" : s.mirrorTitle;
            }
            float clockLeft = drawClock(canvas, w, dp(21), barText, dp(13));
            text.setTextSize(dp(13));
            text.setColor(barText);
            canvas.drawText(clip(text, title, Math.max(0f, clockLeft - dp(12) - dp(30))),
                    dp(30), dp(21), text);
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

    private void drawToast(Canvas canvas, BridgeState s, int w, int h) {
        boolean light = s.lightTheme;
        bg.setColor(light ? 0xFFE8ECF2 : 0xFF10131A);
        canvas.drawRect(0, 0, w, h, bg);
        int usbColor = !s.usbConnected ? 0xFFFF5C7A : (s.clientConnected ? 0xFF3DDC97 : 0xFFFFB020);
        accent.setColor(usbColor);
        canvas.drawCircle(dp(16), dp(16), dp(6), accent);
        String barTitle = "系统弹窗";
        int barText = light ? 0xFF1A2333 : 0xFFE8EEF8;
        float clockLeft = drawClock(canvas, w, dp(21), barText, dp(13));
        text.setTextSize(dp(13));
        text.setColor(barText);
        canvas.drawText(clip(text, barTitle, Math.max(0f, clockLeft - dp(12) - dp(30))),
                dp(30), dp(21), text);

        int cardBg = light ? 0xFFFFFFFF : 0xFF2B2B2B;
        int fg = light ? 0xFF1A1A1A : 0xFFFFFFFF;
        int muted = light ? 0xFF5C5C5C : 0xFFC8C8C8;
        int btnBg = light ? 0xFFF0F0F0 : 0xFF3A3A3A;
        int accentFg = light ? 0xFF0067C0 : 0xFF4CC2FF;
        float pad = dp(18);
        float cardW = Math.min(w - dp(36), dp(420));
        float innerW = cardW - pad * 2f;
        float y = dp(48);
        float x = (w - cardW) / 2f;

        String app = s.toastApp == null ? "" : s.toastApp.trim();
        String title = s.toastTitle == null ? "" : s.toastTitle.trim();
        String body = s.toastBody == null ? "" : s.toastBody.trim();
        String[] labels = s.toastButtonLabels == null ? new String[0] : s.toastButtonLabels;
        int btnN = Math.min(labels.length, toastBtnRects.length);
        toastBtnCount = btnN;

        text.setTextSize(dp(12));
        float appH = app.isEmpty() ? 0f : dp(18);
        text.setTextSize(dp(20));
        float titleH = title.isEmpty() ? 0f : measureWrappedHeight(title, innerW, text, dp(24), 3);
        text.setTextSize(dp(14));
        float bodyH = body.isEmpty() ? 0f : measureWrappedHeight(body, innerW, text, dp(20), 6);
        float btnH = btnN > 0 ? dp(40) : 0f;
        float cardH = pad + appH + titleH + bodyH + (btnN > 0 ? dp(14) + btnH : 0f) + pad;
        if (cardH < dp(120)) {
            cardH = dp(120);
        }
        if (y + cardH > h - dp(28)) {
            cardH = Math.max(dp(100), h - dp(28) - y);
        }
        toastCard.set(x, y, x + cardW, y + cardH);
        cardPaint.setColor(cardBg);
        canvas.drawRoundRect(toastCard, dp(16), dp(16), cardPaint);

        float cy = y + pad;
        if (!app.isEmpty()) {
            text.setTextSize(dp(12));
            text.setColor(muted);
            canvas.drawText(clip(text, app, innerW), x + pad, cy + dp(12), text);
            cy += appH;
        }
        if (!title.isEmpty()) {
            text.setTextSize(dp(20));
            text.setColor(fg);
            cy += drawWrapped(canvas, title, x + pad, cy, innerW, text, dp(24), 3);
        }
        if (!body.isEmpty()) {
            text.setTextSize(dp(14));
            text.setColor(muted);
            cy += drawWrapped(canvas, body, x + pad, cy, innerW, text, dp(20), 6);
        }
        for (int i = 0; i < toastBtnRects.length; i++) {
            toastBtnRects[i].setEmpty();
        }
        if (btnN > 0) {
            float btnY = toastCard.bottom - pad - btnH;
            float right = toastCard.right - pad;
            for (int i = btnN - 1; i >= 0; i--) {
                String label = labels[i] == null ? "" : labels[i];
                text.setTextSize(dp(14));
                float tw = Math.max(dp(56), text.measureText(label) + dp(24));
                float left = right - tw;
                toastBtnRects[i].set(left, btnY, right, btnY + btnH);
                button.setColor(btnBg);
                canvas.drawRoundRect(toastBtnRects[i], dp(8), dp(8), button);
                text.setColor(i == btnN - 1 ? accentFg : fg);
                canvas.drawText(label, toastBtnRects[i].centerX() - text.measureText(label) / 2f,
                        toastBtnRects[i].centerY() + dp(5), text);
                right = left - dp(8);
            }
        }
        text.setColor(colText);
        dim.setTextSize(dp(12));
        dim.setColor(muted);
        String hint = "点按钮即操作电脑通知 · 点空白处关闭";
        float hw = dim.measureText(hint);
        canvas.drawText(hint, w / 2f - hw / 2f, h - dp(14), dim);
        dim.setColor(colDim);
        cardPaint.setColor(light ? 0xFFE8EEF5 : 0xFF1A2438);
        button.setColor(colButton);
    }

    private float measureWrappedHeight(String value, float maxW, Paint paint, float lineH, int maxLines) {
        if (value == null || value.isEmpty()) {
            return 0f;
        }
        int lines = 0;
        String rest = value;
        while (!rest.isEmpty() && lines < maxLines) {
            int count = paint.breakText(rest, true, maxW, null);
            if (count <= 0) {
                break;
            }
            rest = rest.substring(count);
            lines++;
        }
        return Math.max(lineH, lines * lineH);
    }

    private float drawWrapped(Canvas canvas, String value, float x, float y, float maxW,
            Paint paint, float lineH, int maxLines) {
        if (value == null || value.isEmpty()) {
            return 0f;
        }
        int lines = 0;
        String rest = value;
        float top = y;
        while (!rest.isEmpty() && lines < maxLines) {
            int count = paint.breakText(rest, true, maxW, null);
            if (count <= 0) {
                break;
            }
            String line = rest.substring(0, count);
            rest = rest.substring(count);
            if (!rest.isEmpty() && lines == maxLines - 1) {
                line = clip(paint, line + rest, maxW);
                rest = "";
            }
            canvas.drawText(line, x, top + lineH - dp(4), paint);
            top += lineH;
            lines++;
        }
        return lines * lineH;
    }

    private int toastButtonAt(float x, float y) {
        for (int i = 0; i < toastBtnCount; i++) {
            if (toastBtnRects[i].contains(x, y)) {
                return i;
            }
        }
        return -1;
    }

    private void clearToastOverlay() {
        BridgeState s = BridgeService.STATE;
        s.toastOverlay = false;
        s.toastTitle = "";
        s.toastApp = "";
        s.toastBody = "";
        s.toastButtonIds = new String[0];
        s.toastButtonLabels = new String[0];
        toastBtnCount = 0;
        invalidate();
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
            String title = s.hudStyle.title(i, HudStyle.fallbackTitle(metric, s.pcDiskName));
            drawStatCard(canvas, x, top, cardW, cardH, title,
                    formatMetricValue(s, metric),
                    formatMetricFoot(s, metric), metricUsage(s, metric), i);
        }

        dim.setTextSize(dp(12));
        float meterTop = muteTop - meterH;
        canvas.drawText("↓ " + formatRate(s.pcNetDown) + "  ↑ " + formatRate(s.pcNetUp),
                dp(18), meterTop + dp(14), dim);
        playRect.set(dp(210), meterTop, w - dp(18), muteTop - dp(4));
        drawPlayMeter(canvas, s, w);
    }

    private void drawStatCard(Canvas canvas, float x, float y, float cw, float ch,
            String title, String value, String foot, float usage, int slot) {
        tmpRect.set(x, y, x + cw, y + ch);
        canvas.drawRoundRect(tmpRect, dp(12), dp(12), cardPaint);
        HudStyle style = BridgeService.STATE.hudStyle;
        String[] subs = style.displaySubs(slot);
        float padX = dp(10);
        float innerW = Math.max(dp(24), cw - padX * 2);
        float titleSize = dp(13);
        float valueWant = dp(style.valueSize(slot));
        float subWant = dp(style.subSize(slot));
        boolean hasSub = subs.length > 0;
        boolean hasFoot = foot != null && !foot.isEmpty();
        boolean showChart = style.chartOn(slot);
        float barSpace = dp(16);
        float footSpace = hasFoot ? dp(16) : 0;
        float chartMin = showChart ? dp(36) : 0;
        float usableBottom = y + ch - barSpace - footSpace - (showChart ? chartMin + dp(4) : 0);

        int titleColor = style.titleColor(slot);
        dim.setColor(titleColor != 0 ? titleColor : colDim);
        titleSize = fitText(dim, title, innerW, titleSize, dp(9));
        float titleTop = y + dp(8);
        float titleBase = titleTop - dim.ascent();

        int valueColor = style.paintValueColor(slot, usage);
        text.setColor(valueColor);
        valueWant = fitText(text, value, innerW, valueWant, dp(HudStyle.MIN_VALUE_SIZE));
        float afterTitle = titleBase + dim.descent() + dp(4);
        float valueBase = afterTitle - text.ascent();
        float valueBottom = valueBase + text.descent();

        if (hasSub) {
            dim.setColor(colDim);
            for (int i = 0; i < subs.length; i++) {
                String line = formatMetricValue(BridgeService.STATE, subs[i]);
                subWant = fitText(dim, line, innerW, subWant, dp(HudStyle.MIN_SUB_SIZE));
            }
        }

        float[] subBases = new float[subs.length];
        float subBottom = valueBottom;
        if (hasSub) {
            dim.setTextSize(subWant);
            float prev = valueBottom;
            for (int i = 0; i < subs.length; i++) {
                subBases[i] = prev + dp(3) - dim.ascent();
                prev = subBases[i] + dim.descent();
            }
            subBottom = prev;
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
                float prev = valueBottom;
                for (int i = 0; i < subs.length; i++) {
                    subBases[i] = prev + dp(3) - dim.ascent();
                    prev = subBases[i] + dim.descent();
                }
                subBottom = prev;
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
            for (int i = 0; i < subs.length; i++) {
                String line = formatMetricValue(BridgeService.STATE, subs[i]);
                canvas.drawText(clip(dim, line, innerW), x + padX, subBases[i], dim);
            }
        }
        canvas.restore();
        dim.setColor(colDim);

        float barTop = y + ch - dp(14);
        float chartBottom = y + ch - barSpace - footSpace - dp(2);
        if (showChart) {
            float chartTop = subBottom + dp(6);
            if (chartBottom - chartTop >= dp(18)) {
                drawSparkline(canvas, x + dp(10), chartTop, x + cw - dp(10), chartBottom,
                        style.chartMetric(slot), valueColor);
            }
        }
        if (hasFoot) {
            dim.setTextSize(dp(11));
            dim.setColor(colDim);
            canvas.drawText(clip(dim, foot, innerW), x + padX, y + ch - barSpace - dp(2), dim);
        }

        tmpRect.set(x + dp(10), barTop, x + cw - dp(10), barTop + dp(7));
        canvas.drawRoundRect(tmpRect, dp(4), dp(4), meterBg);
        float fill = Float.isNaN(usage) ? 0.04f : Math.max(0.04f, Math.min(1f, usage / 100f));
        meter.setColor(valueColor);
        tmpRect.right = tmpRect.left + Math.max(dp(6), (cw - dp(20)) * fill);
        canvas.drawRoundRect(tmpRect, dp(4), dp(4), meter);
    }

    private void drawSparkline(Canvas canvas, float left, float top, float right, float bottom,
            String metric, int color) {
        float width = right - left;
        float height = bottom - top;
        if (width < dp(12) || height < dp(12)) {
            return;
        }
        sparkStroke.setStrokeWidth(dp(1.5f));
        sparkStroke.setColor(color);
        sparkFill.setColor((color & 0x00FFFFFF) | 0x33000000);
        int n = BridgeService.STATE.sparks.copy(metric, sparkBuf);
        if (n < 2) {
            float mid = (top + bottom) / 2f;
            canvas.drawLine(left, mid, right, mid, sparkStroke);
            return;
        }
        float min = Float.POSITIVE_INFINITY;
        float max = Float.NEGATIVE_INFINITY;
        int valid = 0;
        for (int i = 0; i < n; i++) {
            float v = sparkBuf[i];
            if (Float.isNaN(v)) {
                continue;
            }
            valid++;
            if (v < min) {
                min = v;
            }
            if (v > max) {
                max = v;
            }
        }
        if (valid < 2) {
            float mid = (top + bottom) / 2f;
            canvas.drawLine(left, mid, right, mid, sparkStroke);
            return;
        }
        float lo;
        float hi;
        if (SparkHistory.percentScale(metric)) {
            lo = 0f;
            hi = 100f;
        } else if (SparkHistory.tempScale(metric)) {
            lo = 0f;
            hi = Math.max(100f, max);
        } else {
            float pad = Math.max(1f, (max - min) * 0.15f);
            lo = min - pad;
            hi = max + pad;
            if (lo < 0f && min >= 0f) {
                lo = 0f;
            }
        }
        if (hi - lo < 1f) {
            hi = lo + 1f;
        }
        sparkPath.reset();
        sparkFillPath.reset();
        boolean started = false;
        float firstX = left;
        float lastX = left;
        for (int i = 0; i < n; i++) {
            float v = sparkBuf[i];
            if (Float.isNaN(v)) {
                started = false;
                continue;
            }
            float x = left + width * i / (n - 1f);
            float y = bottom - ((v - lo) / (hi - lo)) * height;
            if (!started) {
                sparkPath.moveTo(x, y);
                sparkFillPath.moveTo(x, bottom);
                sparkFillPath.lineTo(x, y);
                firstX = x;
                started = true;
            } else {
                sparkPath.lineTo(x, y);
                sparkFillPath.lineTo(x, y);
            }
            lastX = x;
        }
        sparkFillPath.lineTo(lastX, bottom);
        sparkFillPath.lineTo(firstX, bottom);
        sparkFillPath.close();
        canvas.drawPath(sparkFillPath, sparkFill);
        canvas.drawPath(sparkPath, sparkStroke);
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
        if (advanceMuteChrome()) {
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
            if (BridgeService.STATE.screenMirror || BridgeService.STATE.toastOverlay) {
                noteMirrorInteract();
            } else if (BridgeService.STATE.autoHideMute) {
                muteRevealTap = muteButtonsHidden();
                noteMuteInteract();
            }
            menu.onDown(x, y, w, event);
            if (menu.blocksHud()) {
                return true;
            }
            if (BridgeService.STATE.toastOverlay) {
                toastPressBtn = toastButtonAt(x, y);
                toastPressOutside = toastPressBtn < 0 && !toastCard.contains(x, y);
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
                cancelPointer();
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
            toastPressBtn = -1;
            toastPressOutside = false;
            cancelPointer();
            return true;
        }
        if (action == MotionEvent.ACTION_UP) {
            touchHandler.removeCallbacks(longPress);
            pressSlot = -1;
            if (menu.onUp(x, y, w, event)) {
                muteRevealTap = false;
                cancelPointer();
                return true;
            }
            if (menu.blocksHud()) {
                cancelPointer();
                return true;
            }
            if (BridgeService.STATE.toastOverlay) {
                int btn = toastButtonAt(x, y);
                if (toastPressBtn >= 0 && btn == toastPressBtn && listener != null) {
                    String[] ids = BridgeService.STATE.toastButtonIds;
                    String[] labels = BridgeService.STATE.toastButtonLabels;
                    String id = (ids != null && btn < ids.length) ? ids[btn] : String.valueOf(btn);
                    String label = (labels != null && btn < labels.length) ? labels[btn] : "";
                    listener.onToastAction(id, label);
                    clearToastOverlay();
                } else if (toastPressOutside && !toastCard.contains(x, y) && listener != null) {
                    listener.onToastDismiss();
                    clearToastOverlay();
                }
                toastPressBtn = -1;
                toastPressOutside = false;
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
        if (BridgeService.STATE.screenMirror || BridgeService.STATE.toastOverlay
                || !BridgeService.STATE.hasPcStats()) {
            return -1;
        }
        for (int i = 0; i < cardRects.length; i++) {
            if (cardRects[i].contains(x, y)) {
                return i;
            }
        }
        return -1;
    }

    private void sendPointer(float x, float y, String act) {
        if (listener == null) {
            return;
        }
        int w = getWidth();
        int h = getHeight();
        if (w <= 0 || h <= 0) {
            return;
        }
        listener.onPointer(x / w, y / h, act);
    }

    private void cancelPointer() {
        if (!pointerDown) {
            return;
        }
        pointerDown = false;
        sendPointer(0f, 0f, "cancel");
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

    private float drawClock(Canvas canvas, int w, float baseline, int color, float size) {
        String clock = clockText();
        if (clock.isEmpty()) {
            return w - dp(22);
        }
        text.setTextSize(size);
        text.setColor(color);
        float tw = text.measureText(clock);
        float x = w - dp(40) - tw;
        canvas.drawText(clock, x, baseline, text);
        text.setColor(colText);
        return x;
    }

    private static String clockText() {
        BridgeState s = BridgeService.STATE;
        if (!s.clockDate && !s.clockHour && !s.clockMinute && !s.clockSecond) {
            return "";
        }
        java.util.Calendar c = clockCalendar(s);
        StringBuilder out = new StringBuilder();
        if (s.clockDate) {
            out.append(c.get(java.util.Calendar.MONTH) + 1)
                    .append("月")
                    .append(c.get(java.util.Calendar.DAY_OF_MONTH))
                    .append("日");
        }
        if (s.clockHour || s.clockMinute || s.clockSecond) {
            if (out.length() > 0) {
                out.append("  ");
            }
            boolean started = false;
            if (s.clockHour) {
                out.append(pad2(c.get(java.util.Calendar.HOUR_OF_DAY)));
                started = true;
            }
            if (s.clockMinute) {
                if (started) {
                    out.append(':');
                }
                out.append(pad2(c.get(java.util.Calendar.MINUTE)));
                started = true;
            }
            if (s.clockSecond) {
                if (started) {
                    out.append(':');
                }
                out.append(pad2(c.get(java.util.Calendar.SECOND)));
            }
        }
        return out.toString();
    }

    private static java.util.Calendar clockCalendar(BridgeState s) {
        if (s.clientConnected && s.pcNowMs > 0 && s.pcNowAt != 0) {
            long ms = s.pcNowMs + (android.os.SystemClock.elapsedRealtime() - s.pcNowAt);
            java.util.Calendar c = java.util.Calendar.getInstance(
                    new java.util.SimpleTimeZone(s.pcTzMin * 60_000, "PC"));
            c.setTimeInMillis(ms);
            return c;
        }
        return java.util.Calendar.getInstance();
    }

    private static String pad2(int value) {
        return value < 10 ? "0" + value : String.valueOf(value);
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

    float dp(float v) {
        return v * getResources().getDisplayMetrics().density;
    }
}
