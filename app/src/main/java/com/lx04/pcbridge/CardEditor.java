package com.lx04.pcbridge;

import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.view.MotionEvent;
import android.view.VelocityTracker;
import android.view.ViewConfiguration;
import android.widget.OverScroller;

final class CardEditor {
    static final int PAGE_MAIN = 0;
    static final int PAGE_METRIC = 1;
    static final int PAGE_SUB = 2;

    private final StatusHudView view;
    private final OverScroller scroller;
    private final int touchSlop;
    private final int minFling;
    private final int maxFling;
    private final Paint dim = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint panel = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint card = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint text = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint label = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint accent = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint scrollBar = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final RectF panelRect = new RectF();
    private final RectF headerRect = new RectF();
    private final RectF viewport = new RectF();
    private final RectF metricRect = new RectF();
    private final RectF subRect = new RectF();
    private final RectF resetRect = new RectF();
    private final RectF doneRect = new RectF();
    private final RectF[] titleSwatches = new RectF[HudStyle.PALETTE.length];
    private final RectF[] valueSwatches = new RectF[HudStyle.PALETTE.length];
    private int slot = -1;
    private int page = PAGE_MAIN;
    private float mainScroll;
    private float listScroll;
    private float contentHeight;
    private float dragStartY;
    private float dragScroll;
    private boolean dragging;
    private boolean light;
    private VelocityTracker velocity;

    CardEditor(StatusHudView view) {
        this.view = view;
        scroller = new OverScroller(view.getContext());
        ViewConfiguration vc = ViewConfiguration.get(view.getContext());
        touchSlop = vc.getScaledTouchSlop();
        minFling = vc.getScaledMinimumFlingVelocity();
        maxFling = vc.getScaledMaximumFlingVelocity();
        text.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        label.setTypeface(Typeface.create("sans-serif", Typeface.NORMAL));
        for (int i = 0; i < titleSwatches.length; i++) {
            titleSwatches[i] = new RectF();
            valueSwatches[i] = new RectF();
        }
    }

    boolean isOpen() {
        return slot >= 0;
    }

    void open(int slot) {
        this.slot = slot;
        page = PAGE_MAIN;
        mainScroll = 0;
        listScroll = 0;
        dragging = false;
        scroller.forceFinished(true);
        view.invalidate();
    }

    void close() {
        slot = -1;
        page = PAGE_MAIN;
        recycleVelocity();
        scroller.forceFinished(true);
        view.invalidate();
    }

    boolean advanceFling() {
        if (!scroller.computeScrollOffset()) {
            return false;
        }
        setScroll(scroller.getCurrY());
        return true;
    }

    void draw(Canvas canvas, int w, int h, boolean lightTheme) {
        if (!isOpen()) {
            return;
        }
        light = lightTheme;
        applyPalette(lightTheme);
        canvas.drawRect(0, 0, w, h, dim);
        float p = dp(10);
        panelRect.set(p, p, w - p, h - p);
        canvas.drawRoundRect(panelRect, dp(16), dp(16), panel);

        headerRect.set(panelRect.left, panelRect.top, panelRect.right, panelRect.top + dp(44));
        String name = HudStyle.DEFAULT_TITLES[Math.max(0, Math.min(3, slot))];
        text.setTextSize(dp(18));
        text.setColor(light ? 0xFF1A2438 : 0xFFE8EEF8);
        canvas.drawText((page == PAGE_MAIN ? "编辑  " : "选择  ") + name,
                panelRect.left + dp(16), headerRect.top + dp(30), text);
        if (page != PAGE_MAIN) {
            label.setTextSize(dp(11));
            label.setColor(light ? 0xFF5A6B84 : 0xFF8FA0BE);
            String hint = "上下滑动查看更多";
            float hw = label.measureText(hint);
            canvas.drawText(hint, panelRect.right - dp(16) - hw, headerRect.top + dp(28), label);
        }

        if (page == PAGE_MAIN) {
            drawMain(canvas);
        } else {
            drawList(canvas, page == PAGE_SUB);
        }
    }

    private void drawMain(Canvas canvas) {
        float btnH = dp(40);
        float footerTop = panelRect.bottom - dp(14) - btnH;
        viewport.set(panelRect.left, headerRect.bottom, panelRect.right, footerTop - dp(8));
        contentHeight = measureMainContent();
        mainScroll = clamp(mainScroll, maxScroll());

        canvas.save();
        canvas.clipRect(viewport);
        layoutMain(canvas, true);
        canvas.restore();
        drawScrollBar(canvas);

        float btnW = (panelRect.width() - dp(44)) / 2f;
        resetRect.set(panelRect.left + dp(16), footerTop, panelRect.left + dp(16) + btnW, footerTop + btnH);
        doneRect.set(resetRect.right + dp(12), footerTop, panelRect.right - dp(16), footerTop + btnH);
        drawButton(canvas, resetRect, "恢复本栏");
        drawButton(canvas, doneRect, "完成");
    }

    private float measureMainContent() {
        return layoutMain(null, false);
    }

    private float layoutMain(Canvas canvas, boolean draw) {
        HudStyle style = BridgeService.STATE.hudStyle;
        float y = viewport.top - (draw ? mainScroll : 0);
        float start = y;
        label.setTextSize(dp(12));
        label.setColor(light ? 0xFF5A6B84 : 0xFF8FA0BE);
        y = drawLabeledRow(canvas, draw, "大字内容", y, metricRect,
                HudStyle.metricLabel(style.metric(slot)));
        y = drawLabeledPalette(canvas, draw, "大字颜色", y, valueSwatches,
                style.valueColor(slot), 0xFF3DDC97);
        y += dp(10);
        y = drawLabeledRow(canvas, draw, "小字内容", y, subRect,
                HudStyle.metricLabel(style.subMetric(slot)));
        y = drawLabeledPalette(canvas, draw, "字母颜色", y, titleSwatches,
                style.titleColor(slot), light ? 0xFF5A6B84 : 0xFF8FA0BE);
        return y - start + dp(8);
    }

    private float drawLabeledRow(Canvas canvas, boolean draw, String caption, float y, RectF rect, String value) {
        if (draw) {
            canvas.drawText(caption, panelRect.left + dp(16), y + dp(12), label);
        }
        y += dp(18);
        rect.set(panelRect.left + dp(16), y, panelRect.right - dp(16), y + dp(40));
        if (draw) {
            drawRow(canvas, rect, value);
        }
        return rect.bottom + dp(12);
    }

    private float drawLabeledPalette(Canvas canvas, boolean draw, String caption, float y,
            RectF[] swatches, int selected, int fallback) {
        if (draw) {
            canvas.drawText(caption, panelRect.left + dp(16), y + dp(12), label);
        }
        y += dp(18);
        return drawPalette(canvas, draw, swatches, y, selected, fallback);
    }

    private void drawList(Canvas canvas, boolean includeNone) {
        viewport.set(panelRect.left + dp(8), headerRect.bottom, panelRect.right - dp(8), panelRect.bottom - dp(10));
        int count = listCount(includeNone);
        float itemH = dp(36);
        contentHeight = count * itemH;
        listScroll = clamp(listScroll, maxScroll());

        canvas.save();
        canvas.clipRect(viewport);
        HudStyle style = BridgeService.STATE.hudStyle;
        String current = includeNone ? style.subMetric(slot) : style.metric(slot);
        for (int i = 0; i < count; i++) {
            String key = listKey(includeNone, i);
            float top = viewport.top - listScroll + i * itemH;
            float bottom = top + itemH;
            if (bottom < viewport.top || top > viewport.bottom) {
                continue;
            }
            boolean on = key.equals(current);
            if (on) {
                card.setColor(light ? 0xFFD5E8DA : 0xFF1E3A2F);
                RectF hit = new RectF(viewport.left + dp(6), top + dp(2), viewport.right - dp(6), bottom - dp(2));
                canvas.drawRoundRect(hit, dp(8), dp(8), card);
            }
            text.setTextSize(dp(15));
            text.setColor(on ? 0xFF3DDC97 : (light ? 0xFF1A2438 : 0xFFE8EEF8));
            canvas.drawText(HudStyle.metricLabel(key), viewport.left + dp(16), top + itemH * 0.68f, text);
        }
        canvas.restore();
        drawScrollBar(canvas);
    }

    private float drawPalette(Canvas canvas, boolean draw, RectF[] swatches, float y, int selected, int fallback) {
        int mark = selected != 0 ? selected : fallback;
        float size = dp(28);
        float gap = dp(8);
        float x = panelRect.left + dp(16);
        float max = panelRect.right - dp(16);
        for (int i = 0; i < swatches.length; i++) {
            if (x + size > max + 0.5f) {
                x = panelRect.left + dp(16);
                y += size + gap;
            }
            swatches[i].set(x, y, x + size, y + size);
            if (draw) {
                accent.setColor(HudStyle.PALETTE[i]);
                canvas.drawRoundRect(swatches[i], dp(6), dp(6), accent);
                if ((HudStyle.PALETTE[i] & 0xFFFFFF) == (mark & 0xFFFFFF)) {
                    accent.setStyle(Paint.Style.STROKE);
                    accent.setStrokeWidth(dp(2));
                    accent.setColor(light ? 0xFF1A2438 : 0xFFE8EEF8);
                    canvas.drawRoundRect(swatches[i], dp(6), dp(6), accent);
                    accent.setStyle(Paint.Style.FILL);
                }
            }
            x += size + gap;
        }
        return y + size;
    }

    private void drawRow(Canvas canvas, RectF rect, String value) {
        card.setColor(light ? 0xFFE8EEF5 : 0xFF1A2438);
        canvas.drawRoundRect(rect, dp(10), dp(10), card);
        text.setTextSize(dp(15));
        text.setColor(light ? 0xFF1A2438 : 0xFFE8EEF8);
        canvas.drawText(value, rect.left + dp(14), rect.top + rect.height() * 0.68f, text);
    }

    private void drawButton(Canvas canvas, RectF rect, String value) {
        card.setColor(light ? 0xFFD3DCE8 : 0xFF223154);
        canvas.drawRoundRect(rect, dp(12), dp(12), card);
        text.setTextSize(dp(15));
        text.setColor(light ? 0xFF1A2438 : 0xFFE8EEF8);
        float tw = text.measureText(value);
        canvas.drawText(value, rect.centerX() - tw / 2f, rect.top + rect.height() * 0.66f, text);
    }

    private void drawScrollBar(Canvas canvas) {
        float viewH = viewport.height();
        if (contentHeight <= viewH + 1f) {
            return;
        }
        float track = viewH;
        float thumb = Math.max(dp(28), track * track / contentHeight);
        float max = contentHeight - viewH;
        float t = max <= 0 ? 0 : getScroll() / max;
        float top = viewport.top + (track - thumb) * t;
        float right = viewport.right - dp(4);
        scrollBar.setColor(light ? 0x668FA0BE : 0x88E8EEF8);
        canvas.drawRoundRect(right - dp(4), top, right, top + thumb, dp(2), dp(2), scrollBar);
    }

    boolean onTouch(MotionEvent event) {
        if (!isOpen()) {
            return false;
        }
        float x = event.getX();
        float y = event.getY();
        int action = event.getActionMasked();
        if (action == MotionEvent.ACTION_DOWN) {
            if (view.getParent() != null) {
                view.getParent().requestDisallowInterceptTouchEvent(true);
            }
            scroller.forceFinished(true);
            dragging = false;
            dragStartY = y;
            dragScroll = getScroll();
            recycleVelocity();
            velocity = VelocityTracker.obtain();
            velocity.addMovement(event);
            return true;
        }
        if (velocity != null) {
            velocity.addMovement(event);
        }
        if (action == MotionEvent.ACTION_MOVE) {
            float dy = y - dragStartY;
            if (!dragging && Math.abs(dy) > touchSlop) {
                dragging = true;
            }
            if (dragging) {
                setScroll(dragScroll - dy);
                view.invalidate();
            }
            return true;
        }
        if (action == MotionEvent.ACTION_CANCEL) {
            recycleVelocity();
            dragging = false;
            return true;
        }
        if (action != MotionEvent.ACTION_UP) {
            return true;
        }
        if (dragging) {
            if (velocity != null) {
                velocity.computeCurrentVelocity(1000, maxFling);
                float vy = velocity.getYVelocity();
                if (Math.abs(vy) > minFling) {
                    scroller.fling(0, Math.round(getScroll()), 0, Math.round(-vy),
                            0, 0, 0, Math.round(maxScroll()));
                    view.postInvalidateOnAnimation();
                }
            }
            recycleVelocity();
            dragging = false;
            return true;
        }
        recycleVelocity();
        if (page != PAGE_MAIN) {
            if (viewport.contains(x, y)) {
                boolean sub = page == PAGE_SUB;
                int count = listCount(sub);
                float itemH = dp(36);
                int index = (int) ((y - viewport.top + listScroll) / itemH);
                if (index >= 0 && index < count) {
                    pickList(sub, index);
                }
                return true;
            }
            page = PAGE_MAIN;
            view.invalidate();
            return true;
        }
        if (metricRect.contains(x, y) && viewport.contains(x, y)) {
            page = PAGE_METRIC;
            listScroll = 0;
            view.invalidate();
            return true;
        }
        if (subRect.contains(x, y) && viewport.contains(x, y)) {
            page = PAGE_SUB;
            listScroll = 0;
            view.invalidate();
            return true;
        }
        HudStyle style = BridgeService.STATE.hudStyle;
        if (viewport.contains(x, y)) {
            for (int i = 0; i < valueSwatches.length; i++) {
                if (valueSwatches[i].contains(x, y)) {
                    style.setValueColor(slot, HudStyle.PALETTE[i]);
                    changed();
                    return true;
                }
            }
            for (int i = 0; i < titleSwatches.length; i++) {
                if (titleSwatches[i].contains(x, y)) {
                    style.setTitleColor(slot, HudStyle.PALETTE[i]);
                    changed();
                    return true;
                }
            }
        }
        if (resetRect.contains(x, y)) {
            style.resetSlot(slot);
            changed();
            return true;
        }
        if (doneRect.contains(x, y) || !panelRect.contains(x, y)) {
            close();
            return true;
        }
        return true;
    }

    private void pickList(boolean sub, int index) {
        String key = listKey(sub, index);
        HudStyle style = BridgeService.STATE.hudStyle;
        if (sub) {
            style.setSubMetric(slot, key);
        } else {
            style.setMetric(slot, key);
        }
        page = PAGE_MAIN;
        changed();
    }

    private void changed() {
        view.onHudEdited();
        view.invalidate();
    }

    private float getScroll() {
        return page == PAGE_MAIN ? mainScroll : listScroll;
    }

    private void setScroll(float value) {
        value = clamp(value, maxScroll());
        if (page == PAGE_MAIN) {
            mainScroll = value;
        } else {
            listScroll = value;
        }
    }

    private float maxScroll() {
        return Math.max(0, contentHeight - viewport.height());
    }

    private static float clamp(float value, float max) {
        if (value < 0) {
            return 0;
        }
        if (value > max) {
            return max;
        }
        return value;
    }

    private int listCount(boolean includeNone) {
        return HudStyle.PICK_METRICS.length + (includeNone ? 1 : 0);
    }

    private String listKey(boolean includeNone, int index) {
        if (includeNone) {
            if (index == 0) {
                return "none";
            }
            return HudStyle.PICK_METRICS[index - 1];
        }
        return HudStyle.PICK_METRICS[index];
    }

    private void applyPalette(boolean lightTheme) {
        dim.setColor(0x99000000);
        if (lightTheme) {
            panel.setColor(0xFFF3F5F8);
            card.setColor(0xFFE8EEF5);
        } else {
            panel.setColor(0xFF141C2E);
            card.setColor(0xFF1A2438);
        }
    }

    private void recycleVelocity() {
        if (velocity != null) {
            velocity.recycle();
            velocity = null;
        }
    }

    private float dp(float v) {
        return view.dp(v);
    }
}
