package com.lx04.pcbridge;

import android.graphics.Canvas;
import android.graphics.DashPathEffect;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.os.SystemClock;
import android.view.MotionEvent;
import android.view.VelocityTracker;
import android.view.ViewConfiguration;

final class AppMenu {
    private static final int PAGE_HUD = 0;
    private static final int PAGE_SETTINGS = 1;
    private static final int PAGE_BG = 2;

    private final StatusHudView view;
    private final int touchSlop;
    private final int minFling;
    private final Paint scrim = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint panel = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint card = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint text = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint dim = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint stroke = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Path chevron = new Path();
    private final RectF drawerRect = new RectF();
    private final RectF settingsRow = new RectF();
    private final RectF hudRow = new RectF();
    private final RectF mirrorRow = new RectF();
    private final RectF backRect = new RectF();
    private final RectF darkRect = new RectF();
    private final RectF lightRect = new RectF();
    private final RectF autoHideOffRect = new RectF();
    private final RectF autoHideOnRect = new RectF();
    private final RectF clockDateRect = new RectF();
    private final RectF clockHourRect = new RectF();
    private final RectF clockMinuteRect = new RectF();
    private final RectF clockSecondRect = new RectF();
    private final RectF settingsPanel = new RectF();
    private final RectF bgRow = new RectF();
    private final RectF[] slotRects = new RectF[] {
            new RectF(), new RectF(), new RectF(), new RectF()
    };
    private final RectF opacityTrack = new RectF();
    private final RectF opacityKnob = new RectF();
    private final Paint dash = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final DashPathEffect dashEffect = new DashPathEffect(new float[] {8f, 6f}, 0);

    private int page = PAGE_HUD;
    private float offset;
    private float target;
    private float drawerW;
    private float downX;
    private float downY;
    private float downOffset;
    private boolean tracking;
    private boolean dragging;
    private boolean animating;
    private boolean light;
    private boolean pageCapture;
    private boolean slidingOpacity;
    private boolean longFired;
    private int pressSlot = -1;
    private long lastAnimMs;
    private long lastOpenMs;
    private VelocityTracker velocity;

    AppMenu(StatusHudView view) {
        this.view = view;
        ViewConfiguration vc = ViewConfiguration.get(view.getContext());
        touchSlop = vc.getScaledTouchSlop();
        minFling = vc.getScaledMinimumFlingVelocity();
        text.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        dim.setTypeface(Typeface.create("sans-serif", Typeface.NORMAL));
        stroke.setStyle(Paint.Style.STROKE);
        stroke.setStrokeCap(Paint.Cap.ROUND);
        stroke.setStrokeJoin(Paint.Join.ROUND);
        dash.setStyle(Paint.Style.STROKE);
        dash.setPathEffect(dashEffect);
    }

    private final Runnable longDelete = new Runnable() {
        @Override
        public void run() {
            if (pressSlot >= 0) {
                BridgeService.deleteHudBg(view.getContext(), pressSlot);
                pressSlot = -1;
                longFired = true;
                view.invalidate();
            }
        }
    };

    boolean blocksHud() {
        return page == PAGE_SETTINGS || page == PAGE_BG || dragging || offset > 1f;
    }

    void close() {
        page = PAGE_HUD;
        tracking = false;
        dragging = false;
        pageCapture = false;
        slidingOpacity = false;
        pressSlot = -1;
        view.removeCallbacks(longDelete);
        recycleVelocity();
        animateTo(0);
        view.invalidate();
    }

    void handleBack() {
        if (dragging || tracking) {
            return;
        }
        if (page == PAGE_BG) {
            page = PAGE_SETTINGS;
            view.invalidate();
            return;
        }
        if (page == PAGE_SETTINGS) {
            page = PAGE_HUD;
            view.invalidate();
            return;
        }
        boolean open = offset > 1f || target > 1f;
        if (open) {
            if (SystemClock.uptimeMillis() - lastOpenMs < 500) {
                return;
            }
            animateTo(0);
            view.invalidate();
            return;
        }
        openDrawer();
    }

    private void openDrawer() {
        int w = view.getWidth();
        if (w <= 0) {
            w = 1;
        }
        drawerW = drawerWidth(w);
        animateTo(drawerW);
        view.invalidate();
    }

    boolean advance() {
        if (!animating) {
            return false;
        }
        long now = SystemClock.uptimeMillis();
        float dt = Math.min(0.05f, (now - lastAnimMs) / 1000f);
        lastAnimMs = now;
        float diff = target - offset;
        if (Math.abs(diff) < 1.5f) {
            offset = target;
            animating = false;
            return false;
        }
        float step = Math.max(dp(420), Math.abs(diff) * 8f) * dt;
        offset += Math.signum(diff) * Math.min(Math.abs(diff), step);
        return true;
    }

    void draw(Canvas canvas, int w, int h, boolean lightTheme) {
        light = lightTheme;
        drawerW = Math.min(dp(208), w * 0.4f);
        if (page == PAGE_BG) {
            drawBgSettings(canvas, w, h);
        } else if (page == PAGE_SETTINGS) {
            drawSettings(canvas, w, h);
        }
        float shown = Math.max(0f, Math.min(drawerW, offset));
        if (shown < 0.5f) {
            return;
        }
        float t = shown / drawerW;
        scrim.setColor(((int) (0x88 * t) << 24));
        canvas.drawRect(0, 0, w, h, scrim);
        drawerRect.set(w - shown, 0, w, h);
        applyPanelColor();
        canvas.drawRoundRect(drawerRect, dp(18), dp(18), panel);
        canvas.drawRect(w - dp(18), 0, w, h, panel);

        float pad = dp(16);
        text.setTextSize(dp(18));
        text.setColor(colText());
        canvas.drawText("菜单", drawerRect.left + pad, dp(36), text);

        settingsRow.set(drawerRect.left + dp(10), dp(56), drawerRect.right - dp(10), dp(108));
        card.setColor(colCard());
        canvas.drawRoundRect(settingsRow, dp(12), dp(12), card);
        text.setTextSize(dp(16));
        canvas.drawText("系统设置", settingsRow.left + dp(14), settingsRow.top + dp(32), text);
        dim.setColor(colDim());
        dim.setTextSize(dp(11));
        canvas.drawText("深色 / 浅色 / 时间 / 背景", settingsRow.left + dp(14), settingsRow.top + dp(46), dim);
        drawChevron(canvas, settingsRow.right - dp(18), settingsRow.centerY(), dp(8), colDim(), false);

        boolean mirroring = BridgeService.STATE.screenMirror;
        hudRow.set(drawerRect.left + dp(10), dp(118), drawerRect.right - dp(10), dp(180));
        mirrorRow.set(drawerRect.left + dp(10), dp(190), drawerRect.right - dp(10), dp(252));
        drawModeRow(canvas, hudRow, "状态监视", "CPU / GPU 占用", !mirroring);
        drawModeRow(canvas, mirrorRow, "屏幕镜像", "投电脑画面", mirroring);

        String ver = formatVersion(BridgeService.STATE.apkVersion);
        dim.setColor(colDim());
        dim.setTextSize(dp(11));
        float vw = dim.measureText(ver);
        canvas.drawText(ver, drawerRect.centerX() - vw / 2f, h - dp(18), dim);
    }

    private void drawSettings(Canvas canvas, int w, int h) {
        scrim.setColor(0xCC000000);
        canvas.drawRect(0, 0, w, h, scrim);
        float p = dp(10);
        settingsPanel.set(p, p, w - p, h - p);
        applyPanelColor();
        canvas.drawRoundRect(settingsPanel, dp(16), dp(16), panel);

        backRect.set(settingsPanel.left, settingsPanel.top, settingsPanel.left + dp(88),
                settingsPanel.top + dp(48));
        text.setColor(colText());
        text.setTextSize(dp(16));
        drawChevron(canvas, backRect.left + dp(22), backRect.centerY(), dp(9), colText(), true);
        canvas.drawText("返回", backRect.left + dp(34), backRect.top + dp(30), text);

        String title = "系统设置";
        text.setTextSize(dp(18));
        float tw = text.measureText(title);
        canvas.drawText(title, settingsPanel.centerX() - tw / 2f, settingsPanel.top + dp(30), text);

        dim.setColor(colDim());
        dim.setTextSize(dp(13));
        canvas.drawText("外观", settingsPanel.left + dp(18), settingsPanel.top + dp(64), dim);

        float top = settingsPanel.top + dp(74);
        float btnH = dp(44);
        float gap = dp(10);
        float inner = settingsPanel.width() - dp(36);
        float btnW = (inner - gap) / 2f;
        darkRect.set(settingsPanel.left + dp(18), top, settingsPanel.left + dp(18) + btnW, top + btnH);
        lightRect.set(darkRect.right + gap, top, darkRect.right + gap + btnW, top + btnH);
        drawModeButton(canvas, darkRect, "深色", !light);
        drawModeButton(canvas, lightRect, "浅色", light);

        dim.setTextSize(dp(12));
        canvas.drawText("与电脑上位机的「浅色」开关同步。",
                settingsPanel.left + dp(18), lightRect.bottom + dp(20), dim);

        dim.setTextSize(dp(13));
        canvas.drawText("静音按钮", settingsPanel.left + dp(18), lightRect.bottom + dp(42), dim);

        float hideTop = lightRect.bottom + dp(50);
        autoHideOffRect.set(settingsPanel.left + dp(18), hideTop,
                settingsPanel.left + dp(18) + btnW, hideTop + btnH);
        autoHideOnRect.set(autoHideOffRect.right + gap, hideTop,
                autoHideOffRect.right + gap + btnW, hideTop + btnH);
        boolean autoHide = BridgeService.STATE.autoHideMute;
        drawModeButton(canvas, autoHideOffRect, "常显", !autoHide);
        drawModeButton(canvas, autoHideOnRect, "自动隐藏", autoHide);

        dim.setTextSize(dp(12));
        canvas.drawText("开启后空闲会隐藏，点屏幕可再次呼出。",
                settingsPanel.left + dp(18), autoHideOnRect.bottom + dp(18), dim);

        dim.setTextSize(dp(13));
        canvas.drawText("时间", settingsPanel.left + dp(18), autoHideOnRect.bottom + dp(42), dim);

        float clockTop = autoHideOnRect.bottom + dp(50);
        float unitW = (inner - gap * 3) / 4f;
        clockDateRect.set(settingsPanel.left + dp(18), clockTop,
                settingsPanel.left + dp(18) + unitW, clockTop + btnH);
        clockHourRect.set(clockDateRect.right + gap, clockTop,
                clockDateRect.right + gap + unitW, clockTop + btnH);
        clockMinuteRect.set(clockHourRect.right + gap, clockTop,
                clockHourRect.right + gap + unitW, clockTop + btnH);
        clockSecondRect.set(clockMinuteRect.right + gap, clockTop,
                clockMinuteRect.right + gap + unitW, clockTop + btnH);
        BridgeState clock = BridgeService.STATE;
        drawModeButton(canvas, clockDateRect, "日期", clock.clockDate);
        drawModeButton(canvas, clockHourRect, "时", clock.clockHour);
        drawModeButton(canvas, clockMinuteRect, "分", clock.clockMinute);
        drawModeButton(canvas, clockSecondRect, "秒", clock.clockSecond);

        dim.setTextSize(dp(12));
        canvas.drawText("右上角逐项开关，全关则不显示。",
                settingsPanel.left + dp(18), clockSecondRect.bottom + dp(18), dim);

        bgRow.set(settingsPanel.left + dp(18), clockSecondRect.bottom + dp(30),
                settingsPanel.right - dp(18), clockSecondRect.bottom + dp(76));
        card.setColor(colCard());
        canvas.drawRoundRect(bgRow, dp(12), dp(12), card);
        text.setTextSize(dp(16));
        text.setColor(colText());
        canvas.drawText("监视页背景", bgRow.left + dp(14), bgRow.top + dp(20), text);
        dim.setColor(colDim());
        dim.setTextSize(dp(11));
        canvas.drawText("自定义图片 / 元素透明度", bgRow.left + dp(14), bgRow.top + dp(36), dim);
        drawChevron(canvas, bgRow.right - dp(18), bgRow.centerY(), dp(8), colDim(), false);
    }

    private void drawBgSettings(Canvas canvas, int w, int h) {
        scrim.setColor(0xCC000000);
        canvas.drawRect(0, 0, w, h, scrim);
        float p = dp(10);
        settingsPanel.set(p, p, w - p, h - p);
        applyPanelColor();
        canvas.drawRoundRect(settingsPanel, dp(16), dp(16), panel);

        backRect.set(settingsPanel.left, settingsPanel.top, settingsPanel.left + dp(88),
                settingsPanel.top + dp(48));
        text.setColor(colText());
        text.setTextSize(dp(16));
        drawChevron(canvas, backRect.left + dp(22), backRect.centerY(), dp(9), colText(), true);
        canvas.drawText("返回", backRect.left + dp(34), backRect.top + dp(32), text);

        String title = "监视页背景";
        text.setTextSize(dp(18));
        float tw = text.measureText(title);
        canvas.drawText(title, settingsPanel.centerX() - tw / 2f, settingsPanel.top + dp(32), text);

        dim.setColor(colDim());
        dim.setTextSize(dp(13));
        canvas.drawText("背景库", settingsPanel.left + dp(18), settingsPanel.top + dp(72), dim);

        float gap = dp(8);
        float inner = settingsPanel.width() - dp(36);
        float slotW = (inner - gap * 3) / 4f;
        float slotH = dp(68);
        float slotTop = settingsPanel.top + dp(84);
        int selected = HudBackground.INSTANCE.selected();
        String[] labels = new String[] {"默认", "背景 1", "背景 2", "背景 3"};
        for (int i = 0; i < 4; i++) {
            float left = settingsPanel.left + dp(18) + (slotW + gap) * i;
            slotRects[i].set(left, slotTop, left + slotW, slotTop + slotH);
            boolean sel = i == 0 ? selected == HudBackground.NONE : selected == i - 1;
            drawBgSlot(canvas, slotRects[i], i, labels[i], sel);
        }

        dim.setTextSize(dp(12));
        canvas.drawText("点选使用。长按已存背景可删除。",
                settingsPanel.left + dp(18), slotTop + slotH + dp(22), dim);
        canvas.drawText("图片从电脑上位机上传，最多 3 张。",
                settingsPanel.left + dp(18), slotTop + slotH + dp(40), dim);

        dim.setTextSize(dp(13));
        float opTop = slotTop + slotH + dp(62);
        canvas.drawText("元素不透明度", settingsPanel.left + dp(18), opTop, dim);
        int alpha = HudBackground.INSTANCE.alpha();
        String pct = alpha + "%";
        text.setTextSize(dp(14));
        text.setColor(colText());
        float pw = text.measureText(pct);
        canvas.drawText(pct, settingsPanel.right - dp(18) - pw, opTop, text);

        float trackH = dp(8);
        float trackTop = opTop + dp(16);
        opacityTrack.set(settingsPanel.left + dp(18), trackTop,
                settingsPanel.right - dp(18), trackTop + trackH);
        card.setColor(light ? 0xFFD5DDE8 : 0xFF1E2A44);
        canvas.drawRoundRect(opacityTrack, dp(4), dp(4), card);
        float t = (alpha - HudBackground.MIN_ALPHA)
                / (float) (HudBackground.MAX_ALPHA - HudBackground.MIN_ALPHA);
        float fillRight = opacityTrack.left + opacityTrack.width() * Math.max(0f, Math.min(1f, t));
        tmpFill(canvas, opacityTrack.left, opacityTrack.top, fillRight, opacityTrack.bottom, 0xFF3DDC97);
        float knob = dp(16);
        float kx = fillRight;
        opacityKnob.set(kx - knob / 2f, opacityTrack.centerY() - knob / 2f,
                kx + knob / 2f, opacityTrack.centerY() + knob / 2f);
        card.setColor(0xFF3DDC97);
        canvas.drawRoundRect(opacityKnob, knob / 2f, knob / 2f, card);

        dim.setTextSize(dp(12));
        dim.setColor(colDim());
        canvas.drawText("卡片和按钮变透明，背景图保持清晰。",
                settingsPanel.left + dp(18), opacityTrack.bottom + dp(26), dim);
    }

    private void tmpFill(Canvas canvas, float l, float t, float r, float b, int color) {
        if (r <= l) {
            return;
        }
        int prev = card.getColor();
        card.setColor(color);
        canvas.drawRoundRect(l, t, r, b, dp(4), dp(4), card);
        card.setColor(prev);
    }

    private void drawBgSlot(Canvas canvas, RectF rect, int index, String label, boolean selected) {
        boolean filled = index > 0 && HudBackground.INSTANCE.used(index - 1);
        if (selected) {
            card.setColor(light ? 0xFFD7F6E7 : 0xFF1C3A32);
            stroke.setStrokeWidth(dp(2));
            stroke.setColor(0xFF3DDC97);
        } else {
            card.setColor(colCard());
            stroke.setStrokeWidth(dp(1));
            stroke.setColor(light ? 0xFFD3DCE8 : 0xFF2A3A58);
        }
        canvas.drawRoundRect(rect, dp(10), dp(10), card);
        RectF inner = new RectF(rect.left + dp(6), rect.top + dp(6),
                rect.right - dp(6), rect.bottom - dp(22));
        if (index == 0) {
            card.setColor(light ? 0xFFF3F5F8 : 0xFF0B1220);
            canvas.drawRoundRect(inner, dp(6), dp(6), card);
        } else if (filled) {
            canvas.save();
            canvas.clipRect(inner);
            HudBackground.INSTANCE.drawThumbnail(canvas, index - 1, inner);
            canvas.restore();
        } else {
            dash.setStrokeWidth(dp(1.2f));
            dash.setColor(light ? 0xFFB7C4D6 : 0xFF3A4C6A);
            canvas.drawRoundRect(inner, dp(6), dp(6), dash);
            dim.setColor(colDim());
            dim.setTextSize(dp(11));
            String empty = "空";
            float ew = dim.measureText(empty);
            canvas.drawText(empty, inner.centerX() - ew / 2f, inner.centerY() + dp(4), dim);
        }
        canvas.drawRoundRect(rect, dp(10), dp(10), stroke);
        text.setTextSize(dp(11));
        text.setColor(selected ? 0xFF3DDC97 : colText());
        float lw = text.measureText(label);
        canvas.drawText(label, rect.centerX() - lw / 2f, rect.bottom - dp(7), text);
        text.setColor(colText());
    }

    private void drawModeButton(Canvas canvas, RectF rect, String label, boolean selected) {
        if (selected) {
            card.setColor(light ? 0xFFD7F6E7 : 0xFF1C3A32);
            stroke.setStrokeWidth(dp(2));
            stroke.setColor(0xFF3DDC97);
        } else {
            card.setColor(colCard());
            stroke.setStrokeWidth(dp(1));
            stroke.setColor(light ? 0xFFD3DCE8 : 0xFF2A3A58);
        }
        canvas.drawRoundRect(rect, dp(12), dp(12), card);
        canvas.drawRoundRect(rect, dp(12), dp(12), stroke);
        text.setTextSize(dp(16));
        text.setColor(selected ? 0xFF3DDC97 : colText());
        float tw = text.measureText(label);
        canvas.drawText(label, rect.centerX() - tw / 2f, rect.top + rect.height() * 0.64f, text);
    }

    private void drawChevron(Canvas canvas, float x, float y, float size, int color, boolean left) {
        chevron.reset();
        if (left) {
            chevron.moveTo(x + size * 0.35f, y - size);
            chevron.lineTo(x - size * 0.55f, y);
            chevron.lineTo(x + size * 0.35f, y + size);
        } else {
            chevron.moveTo(x - size * 0.35f, y - size);
            chevron.lineTo(x + size * 0.55f, y);
            chevron.lineTo(x - size * 0.35f, y + size);
        }
        stroke.setStyle(Paint.Style.STROKE);
        stroke.setStrokeWidth(dp(2.2f));
        stroke.setColor(color);
        canvas.drawPath(chevron, stroke);
    }

    boolean onDown(float x, float y, int w, MotionEvent event) {
        downX = x;
        downY = y;
        downOffset = offset;
        dragging = false;
        animating = false;
        pageCapture = false;
        slidingOpacity = false;
        longFired = false;
        pressSlot = -1;
        view.removeCallbacks(longDelete);
        obtainVelocity().addMovement(event);
        drawerW = drawerWidth(w);
        if (page == PAGE_BG && hitOpacity(x, y)) {
            pageCapture = true;
            slidingOpacity = true;
            setOpacityFromX(x);
            tracking = true;
            return true;
        }
        if (page == PAGE_BG) {
            int slot = slotAt(x, y);
            if (slot >= 0 && HudBackground.INSTANCE.used(slot)) {
                pressSlot = slot;
                view.postDelayed(longDelete, 450);
            }
        }
        boolean edge = x >= w - edgeWidth(w);
        tracking = blocksHud() || edge;
        return tracking;
    }

    boolean onMove(float x, float y, int w, MotionEvent event) {
        if (pageCapture && slidingOpacity) {
            setOpacityFromX(x);
            return true;
        }
        if (!tracking && !blocksHud()) {
            return false;
        }
        obtainVelocity().addMovement(event);
        float dx = downX - x;
        float adx = Math.abs(dx);
        float ady = Math.abs(y - downY);
        if (!dragging) {
            if (adx < touchSlop && ady < touchSlop) {
                return pageCapture;
            }
            if (pressSlot >= 0) {
                view.removeCallbacks(longDelete);
                pressSlot = -1;
            }
            if (page == PAGE_SETTINGS || page == PAGE_BG) {
                if (adx < ady || adx < touchSlop) {
                    return true;
                }
            } else if (adx < touchSlop || adx < ady) {
                return false;
            }
            dragging = true;
        }
        offset = clamp(downOffset + dx, 0, drawerWidth(w));
        view.invalidate();
        return true;
    }

    boolean onUp(float x, float y, int w, MotionEvent event) {
        view.removeCallbacks(longDelete);
        if (pageCapture) {
            pageCapture = false;
            slidingOpacity = false;
            recycleVelocity();
            tracking = false;
            dragging = false;
            return true;
        }
        if (!tracking && !blocksHud()) {
            recycleVelocity();
            return false;
        }
        obtainVelocity().addMovement(event);
        obtainVelocity().computeCurrentVelocity(1000);
        float vx = obtainVelocity().getXVelocity();
        recycleVelocity();
        boolean wasDrag = dragging;
        dragging = false;
        tracking = false;
        if (wasDrag) {
            pressSlot = -1;
            snap(w, vx);
            return true;
        }
        if (offset > 1f) {
            if (settingsRow.contains(x, y)) {
                openSettings();
                return true;
            }
            if (hudRow.contains(x, y)) {
                setMirror(false);
                return true;
            }
            if (mirrorRow.contains(x, y)) {
                setMirror(true);
                return true;
            }
            if (!drawerRect.contains(x, y)) {
                animateTo(0);
            } else {
                animateTo(drawerWidth(w));
            }
            view.invalidate();
            return true;
        }
        if (page == PAGE_SETTINGS) {
            if (backRect.contains(x, y)) {
                page = PAGE_HUD;
                view.invalidate();
                return true;
            }
            if (darkRect.contains(x, y)) {
                setLight(false);
                return true;
            }
            if (lightRect.contains(x, y)) {
                setLight(true);
                return true;
            }
            if (autoHideOffRect.contains(x, y)) {
                setAutoHideMute(false);
                return true;
            }
            if (autoHideOnRect.contains(x, y)) {
                setAutoHideMute(true);
                return true;
            }
            if (clockDateRect.contains(x, y)) {
                BridgeService.setClockDate(view.getContext(), !BridgeService.STATE.clockDate);
                view.invalidate();
                return true;
            }
            if (clockHourRect.contains(x, y)) {
                BridgeService.setClockHour(view.getContext(), !BridgeService.STATE.clockHour);
                view.invalidate();
                return true;
            }
            if (clockMinuteRect.contains(x, y)) {
                BridgeService.setClockMinute(view.getContext(), !BridgeService.STATE.clockMinute);
                view.invalidate();
                return true;
            }
            if (clockSecondRect.contains(x, y)) {
                BridgeService.setClockSecond(view.getContext(), !BridgeService.STATE.clockSecond);
                view.invalidate();
                return true;
            }
            if (bgRow.contains(x, y)) {
                openBgSettings();
                return true;
            }
            return true;
        }
        if (page == PAGE_BG) {
            if (longFired) {
                longFired = false;
                return true;
            }
            if (backRect.contains(x, y)) {
                page = PAGE_SETTINGS;
                view.invalidate();
                return true;
            }
            if (slotRects[0].contains(x, y)) {
                BridgeService.setHudBgSlot(view.getContext(), HudBackground.NONE);
                view.invalidate();
                return true;
            }
            int slot = slotAt(x, y);
            if (slot >= 0 && HudBackground.INSTANCE.used(slot)) {
                BridgeService.setHudBgSlot(view.getContext(), slot);
                view.invalidate();
            }
            return true;
        }
        return false;
    }

    void onCancel() {
        view.removeCallbacks(longDelete);
        pageCapture = false;
        slidingOpacity = false;
        pressSlot = -1;
        tracking = false;
        dragging = false;
        recycleVelocity();
        if (offset > 1f && offset < drawerW) {
            animateTo(offset >= drawerW * 0.4f ? drawerW : 0);
        }
        view.invalidate();
    }

    private void openBgSettings() {
        page = PAGE_BG;
        view.invalidate();
    }

    private boolean hitOpacity(float x, float y) {
        float pad = dp(14);
        return x >= opacityTrack.left - pad && x <= opacityTrack.right + pad
                && y >= opacityTrack.top - pad && y <= opacityTrack.bottom + pad;
    }

    private void setOpacityFromX(float x) {
        float t = (x - opacityTrack.left) / Math.max(1f, opacityTrack.width());
        if (t < 0f) {
            t = 0f;
        } else if (t > 1f) {
            t = 1f;
        }
        int alpha = Math.round(HudBackground.MIN_ALPHA
                + t * (HudBackground.MAX_ALPHA - HudBackground.MIN_ALPHA));
        BridgeService.setHudBgAlpha(view.getContext(), alpha);
        view.invalidate();
    }

    private int slotAt(float x, float y) {
        for (int i = 1; i < slotRects.length; i++) {
            if (slotRects[i].contains(x, y)) {
                return i - 1;
            }
        }
        return -1;
    }

    private void openSettings() {
        page = PAGE_SETTINGS;
        animateTo(0);
        view.invalidate();
    }

    private void setMirror(boolean on) {
        BridgeService.setScreenMirror(view.getContext(), on);
        animateTo(0);
        view.invalidate();
    }

    private void drawModeRow(Canvas canvas, RectF rect, String title, String hint, boolean selected) {
        if (selected) {
            card.setColor(light ? 0xFFD7F6E7 : 0xFF1C3A32);
            stroke.setStyle(Paint.Style.STROKE);
            stroke.setStrokeWidth(dp(2));
            stroke.setColor(0xFF3DDC97);
            canvas.drawRoundRect(rect, dp(12), dp(12), card);
            canvas.drawRoundRect(rect, dp(12), dp(12), stroke);
        } else {
            card.setColor(colCard());
            canvas.drawRoundRect(rect, dp(12), dp(12), card);
        }
        text.setTextSize(dp(16));
        text.setColor(selected ? 0xFF3DDC97 : colText());
        canvas.drawText(title, rect.left + dp(14), rect.top + dp(32), text);
        dim.setColor(selected ? 0xFF3DDC97 : colDim());
        dim.setTextSize(dp(11));
        canvas.drawText(hint, rect.left + dp(14), rect.top + dp(50), dim);
        text.setColor(colText());
    }

    private void setLight(boolean wantLight) {
        BridgeService.setLightTheme(view.getContext(), wantLight);
        view.invalidate();
    }

    private void setAutoHideMute(boolean on) {
        BridgeService.setAutoHideMute(view.getContext(), on);
        view.onMuteAutoHideChanged();
        view.invalidate();
    }

    private void snap(int w, float vx) {
        float width = drawerWidth(w);
        if (vx < -minFling) {
            animateTo(width);
        } else if (vx > minFling) {
            animateTo(0);
        } else {
            animateTo(offset >= width * 0.4f ? width : 0);
        }
        view.invalidate();
    }

    private void animateTo(float value) {
        target = value;
        lastAnimMs = SystemClock.uptimeMillis();
        if (value > 1f) {
            lastOpenMs = lastAnimMs;
        }
        animating = Math.abs(offset - target) > 1f;
        if (!animating) {
            offset = target;
        }
        view.postInvalidateOnAnimation();
    }

    private float drawerWidth(int w) {
        return Math.min(dp(208), w * 0.4f);
    }

    private float edgeWidth(int w) {
        return Math.max(dp(28), w * 0.12f);
    }

    private VelocityTracker obtainVelocity() {
        if (velocity == null) {
            velocity = VelocityTracker.obtain();
        }
        return velocity;
    }

    private void recycleVelocity() {
        if (velocity != null) {
            velocity.recycle();
            velocity = null;
        }
    }

    private void applyPanelColor() {
        panel.setColor(light ? 0xFFF7F8FB : 0xFF141C2E);
    }

    private int colText() {
        return light ? 0xFF1A2438 : 0xFFE8EEF8;
    }

    private int colDim() {
        return light ? 0xFF5A6B84 : 0xFF8FA0BE;
    }

    private int colCard() {
        return light ? 0xFFE8EEF5 : 0xFF1A2438;
    }

    private static float clamp(float value, float min, float max) {
        if (value < min) {
            return min;
        }
        if (value > max) {
            return max;
        }
        return value;
    }

    private static String formatVersion(String apkVersion) {
        if (apkVersion == null || apkVersion.isEmpty()) {
            return "v?";
        }
        return apkVersion.startsWith("v") || apkVersion.startsWith("V") ? apkVersion : "v" + apkVersion;
    }

    private float dp(float v) {
        return view.dp(v);
    }
}
