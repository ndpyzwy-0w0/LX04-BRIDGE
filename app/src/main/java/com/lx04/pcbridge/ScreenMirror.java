package com.lx04.pcbridge;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.RectF;
import android.os.SystemClock;

final class ScreenMirror {
    static final ScreenMirror INSTANCE = new ScreenMirror();

    private final Object lock = new Object();
    private final Paint paint = new Paint(Paint.FILTER_BITMAP_FLAG);
    private final RectF dest = new RectF();
    private final BitmapFactory.Options options = new BitmapFactory.Options();
    private Bitmap bitmap;
    private long frameAt;

    private ScreenMirror() {
        options.inPreferredConfig = Bitmap.Config.RGB_565;
    }

    void accept(byte[] jpeg) {
        if (jpeg == null || jpeg.length < 24) {
            return;
        }
        Bitmap next = BitmapFactory.decodeByteArray(jpeg, 0, jpeg.length, options);
        if (next == null) {
            return;
        }
        synchronized (lock) {
            Bitmap old = bitmap;
            bitmap = next;
            frameAt = SystemClock.elapsedRealtime();
            if (old != null && old != next) {
                old.recycle();
            }
        }
    }

    void clear() {
        synchronized (lock) {
            if (bitmap != null) {
                bitmap.recycle();
                bitmap = null;
            }
            frameAt = 0;
        }
    }

    boolean hasFrame() {
        synchronized (lock) {
            return bitmap != null && !bitmap.isRecycled();
        }
    }

    boolean stale() {
        long at = frameAt;
        return at != 0 && SystemClock.elapsedRealtime() - at > 2500;
    }

    void draw(Canvas canvas, int w, int h) {
        synchronized (lock) {
            if (bitmap == null || bitmap.isRecycled()) {
                return;
            }
            dest.set(0, 0, w, h);
            canvas.drawBitmap(bitmap, null, dest, paint);
        }
    }
}
