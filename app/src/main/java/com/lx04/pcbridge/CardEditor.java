package com.lx04.pcbridge;

import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.view.MotionEvent;

final class CardEditor {
    static final int PAGE_MAIN = 0;
    static final int PAGE_METRIC = 1;
    static final int PAGE_SUB = 2;

    private final StatusHudView view;
    private final Paint dim = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint panel = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint card = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint text = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint label = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint accent = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final RectF panelRect = new RectF();
    private final RectF metricRect = new RectF();
    private final RectF subRect = new RectF();
    private final RectF resetRect = new RectF();
    private final RectF doneRect = new RectF();
    private final RectF listRect = new RectF();
    private final RectF[] titleSwatches = new RectF[HudStyle.PALETTE.length];
    private final RectF[] valueSwatches = new RectF[HudStyle.PALETTE.length];
    private int slot = -1;
    private int page = PAGE_MAIN;
    private float scroll;
    private float dragStartY;
    private float dragScroll;
    private boolean dragging;
    private float downX;
    private float downY;
    private boolean light;

    CardEditor(StatusHudView view) {
        this.view = view;
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
        scroll = 0;
        dragging = false;
        view.invalidate();
    }

    void close() {
        slot = -1;
        page = PAGE_MAIN;
        view.invalidate();
    }

    void draw(Canvas canvas, int w, int h, boolean lightTheme) {
        if (!isOpen()) {
            return;
        }
        light = lightTheme;
        applyPalette(lightTheme);
        canvas.drawRect(0, 0, w, h, dim);
        float p = dp(16);
        panelRect.set(p, dp(28), w - p, h - dp(72));
        canvas.drawRoundRect(panelRect, dp(16), dp(16), panel);

        String name = HudStyle.DEFAULT_TITLES[Math.max(0, Math.min(3, slot))];
        text.setTextSize(dp(18));
        text.setColor(light ? 0xFF1A2438 : 0xFFE8EEF8);
        canvas.drawText("编辑  " + name, panelRect.left + dp(18), panelRect.top + dp(32), text);

        if (page == PAGE_MAIN) {
            drawMain(canvas);
        } else {
            drawList(canvas, page == PAGE_SUB);
        }
    }

    private void drawMain(Canvas canvas) {
        HudStyle style = BridgeService.STATE.hudStyle;
        float y = panelRect.top + dp(52);
        label.setTextSize(dp(12));
        label.setColor(light ? 0xFF5A6B84 : 0xFF8FA0BE);
        canvas.drawText("大字内容", panelRect.left + dp(18), y, label);
        y += dp(8);
        setRow(metricRect, y, dp(40));
        drawRow(canvas, metricRect, HudStyle.metricLabel(style.metric(slot)));
        y = metricRect.bottom + dp(14);
        canvas.drawText("大字颜色", panelRect.left + dp(18), y, label);
        y += dp(8);
        y = drawPalette(canvas, valueSwatches, y, style.valueColor(slot), 0xFF3DDC97);
        y += dp(16);
        canvas.drawText("小字内容", panelRect.left + dp(18), y, label);
        y += dp(8);
        setRow(subRect, y, dp(40));
        drawRow(canvas, subRect, HudStyle.metricLabel(style.subMetric(slot)));
        y = subRect.bottom + dp(14);
        canvas.drawText("字母颜色", panelRect.left + dp(18), y, label);
        y += dp(8);
        y = drawPalette(canvas, titleSwatches, y, style.titleColor(slot), light ? 0xFF5A6B84 : 0xFF8FA0BE);

        float btnW = (panelRect.width() - dp(48)) / 2f;
        float btnH = dp(40);
        float btnTop = Math.min(y + dp(18), panelRect.bottom - dp(18) - btnH);
        resetRect.set(panelRect.left + dp(18), btnTop, panelRect.left + dp(18) + btnW, btnTop + btnH);
        doneRect.set(resetRect.right + dp(12), btnTop, panelRect.right - dp(18), btnTop + btnH);
        drawButton(canvas, resetRect, "恢复本栏");
        drawButton(canvas, doneRect, "完成");
    }

    private void drawList(Canvas canvas, boolean includeNone) {
        label.setTextSize(dp(12));
        label.setColor(light ? 0xFF5A6B84 : 0xFF8FA0BE);
        canvas.drawText("点选一项，或点空白处返回", panelRect.left + dp(18), panelRect.top + dp(52), label);
        listRect.set(panelRect.left + dp(12), panelRect.top + dp(64), panelRect.right - dp(12), panelRect.bottom - dp(12));
        int count = listCount(includeNone);
        float itemH = dp(36);
        float maxScroll = Math.max(0, count * itemH - listRect.height());
        if (scroll > maxScroll) {
            scroll = maxScroll;
        }
        if (scroll < 0) {
            scroll = 0;
        }
        canvas.save();
        canvas.clipRect(listRect);
        HudStyle style = BridgeService.STATE.hudStyle;
        String current = includeNone ? style.subMetric(slot) : style.metric(slot);
        for (int i = 0; i < count; i++) {
            String key = listKey(includeNone, i);
            float top = listRect.top - scroll + i * itemH;
            float bottom = top + itemH;
            if (bottom < listRect.top || top > listRect.bottom) {
                continue;
            }
            boolean on = key.equals(current);
            if (on) {
                card.setColor(light ? 0xFFD5E8DA : 0xFF1E3A2F);
                RectF hit = new RectF(listRect.left, top + dp(2), listRect.right, bottom - dp(2));
                canvas.drawRoundRect(hit, dp(8), dp(8), card);
            }
            text.setTextSize(dp(15));
            text.setColor(on ? 0xFF3DDC97 : (light ? 0xFF1A2438 : 0xFFE8EEF8));
            canvas.drawText(HudStyle.metricLabel(key), listRect.left + dp(14), top + itemH * 0.68f, text);
        }
        canvas.restore();
    }

    private float drawPalette(Canvas canvas, RectF[] swatches, float y, int selected, int fallback) {
        int mark = selected != 0 ? selected : fallback;
        float size = dp(28);
        float gap = dp(8);
        float x = panelRect.left + dp(18);
        float max = panelRect.right - dp(18);
        for (int i = 0; i < swatches.length; i++) {
            if (x + size > max + 0.5f) {
                x = panelRect.left + dp(18);
                y += size + gap;
            }
            swatches[i].set(x, y, x + size, y + size);
            accent.setColor(HudStyle.PALETTE[i]);
            canvas.drawRoundRect(swatches[i], dp(6), dp(6), accent);
            if ((HudStyle.PALETTE[i] & 0xFFFFFF) == (mark & 0xFFFFFF)) {
                accent.setStyle(Paint.Style.STROKE);
                accent.setStrokeWidth(dp(2));
                accent.setColor(light ? 0xFF1A2438 : 0xFFE8EEF8);
                canvas.drawRoundRect(swatches[i], dp(6), dp(6), accent);
                accent.setStyle(Paint.Style.FILL);
            }
            x += size + gap;
        }
        return y + size;
    }

    private void setRow(RectF rect, float y, float h) {
        rect.set(panelRect.left + dp(18), y, panelRect.right - dp(18), y + h);
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

    boolean onTouch(MotionEvent event) {
        if (!isOpen()) {
            return false;
        }
        float x = event.getX();
        float y = event.getY();
        int action = event.getAction();
        if (action == MotionEvent.ACTION_DOWN) {
            downX = x;
            downY = y;
            dragging = false;
            if (page != PAGE_MAIN && listRect.contains(x, y)) {
                dragStartY = y;
                dragScroll = scroll;
            }
            return true;
        }
        if (action == MotionEvent.ACTION_MOVE) {
            if (page != PAGE_MAIN && listRect.contains(downX, downY)) {
                float dy = y - dragStartY;
                if (Math.abs(dy) > dp(8)) {
                    dragging = true;
                }
                if (dragging) {
                    scroll = dragScroll - dy;
                    view.invalidate();
                }
            }
            return true;
        }
        if (action != MotionEvent.ACTION_UP) {
            return true;
        }
        if (page != PAGE_MAIN) {
            if (dragging) {
                return true;
            }
            if (listRect.contains(x, y)) {
                boolean sub = page == PAGE_SUB;
                int count = listCount(sub);
                float itemH = dp(36);
                int index = (int) ((y - listRect.top + scroll) / itemH);
                if (index >= 0 && index < count) {
                    pickList(sub, index);
                }
                return true;
            }
            page = PAGE_MAIN;
            view.invalidate();
            return true;
        }
        if (metricRect.contains(x, y)) {
            page = PAGE_METRIC;
            scroll = 0;
            view.invalidate();
            return true;
        }
        if (subRect.contains(x, y)) {
            page = PAGE_SUB;
            scroll = 0;
            view.invalidate();
            return true;
        }
        HudStyle style = BridgeService.STATE.hudStyle;
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

    private float dp(float v) {
        return view.dp(v);
    }
}
