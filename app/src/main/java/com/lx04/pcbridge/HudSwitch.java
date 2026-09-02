package com.lx04.pcbridge;

import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.RectF;

final class HudSwitch {
    private static final RectF TRACK = new RectF();

    static void draw(Canvas canvas, RectF row, boolean on, boolean light, float density,
            Paint fill, Paint thumb) {
        float w = 48f * density;
        float h = 28f * density;
        float top = row.centerY() - h / 2f;
        TRACK.set(row.right - w, top, row.right, top + h);
        int oldFill = fill.getColor();
        int oldThumb = thumb.getColor();
        fill.setColor(on ? 0xFF3DDC97 : (light ? 0xFFD3DCE8 : 0xFF3A4C6A));
        canvas.drawRoundRect(TRACK, h / 2f, h / 2f, fill);
        float pad = Math.max(2f, h * 0.12f);
        float d = h - pad * 2f;
        float left = on ? TRACK.right - pad - d : TRACK.left + pad;
        thumb.setColor(0xFFFFFFFF);
        canvas.drawRoundRect(left, TRACK.top + pad, left + d, TRACK.bottom - pad, d / 2f, d / 2f, thumb);
        fill.setColor(oldFill);
        thumb.setColor(oldThumb);
    }
}
