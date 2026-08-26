package com.lx04.pcbridge;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.RectF;
import android.os.SystemClock;
import android.view.View;

final class ScreenMirror {
    static final ScreenMirror INSTANCE = new ScreenMirror();

    private final Object lock = new Object();
    private final Object inLock = new Object();
    private final Paint paint = new Paint();
    private final RectF dest = new RectF();
    private final BitmapFactory.Options options = new BitmapFactory.Options();
    private Bitmap bitmap;
    private long frameAt;
    private byte[] pending;
    private Thread decoder;
    private volatile boolean running;
    private volatile View host;

    private ScreenMirror() {
        options.inPreferredConfig = Bitmap.Config.RGB_565;
        options.inDither = false;
        options.inScaled = false;
        paint.setFilterBitmap(false);
    }

    void attach(View view) {
        host = view;
    }

    void accept(byte[] jpeg) {
        if (jpeg == null || jpeg.length < 24) {
            return;
        }
        synchronized (inLock) {
            pending = jpeg;
            inLock.notify();
        }
        startDecoder();
    }

    void clear() {
        running = false;
        synchronized (inLock) {
            pending = null;
            inLock.notifyAll();
        }
        Thread thread = decoder;
        decoder = null;
        if (thread != null) {
            thread.interrupt();
            try {
                thread.join(300);
            } catch (InterruptedException ignored) {
            }
        }
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
        return at != 0 && SystemClock.elapsedRealtime() - at > 1500;
    }

    void draw(Canvas canvas, int w, int h) {
        synchronized (lock) {
            if (bitmap == null || bitmap.isRecycled()) {
                return;
            }
            dest.set(0, 0, w, h);
            boolean scale = bitmap.getWidth() != w || bitmap.getHeight() != h;
            paint.setFilterBitmap(scale);
            canvas.drawBitmap(bitmap, null, dest, paint);
        }
    }

    private void startDecoder() {
        synchronized (this) {
            if (decoder != null && decoder.isAlive()) {
                return;
            }
            running = true;
            decoder = new Thread(this::decodeLoop, "lx04-mirror");
            decoder.start();
        }
    }

    private void decodeLoop() {
        while (running) {
            byte[] jpeg;
            synchronized (inLock) {
                while (running && pending == null) {
                    try {
                        inLock.wait();
                    } catch (InterruptedException e) {
                        return;
                    }
                }
                jpeg = pending;
                pending = null;
            }
            if (!running || jpeg == null) {
                continue;
            }
            Bitmap next = BitmapFactory.decodeByteArray(jpeg, 0, jpeg.length, options);
            if (next == null) {
                continue;
            }
            if (!running) {
                next.recycle();
                continue;
            }
            synchronized (lock) {
                if (!running) {
                    next.recycle();
                    continue;
                }
                Bitmap old = bitmap;
                bitmap = next;
                frameAt = SystemClock.elapsedRealtime();
                if (old != null && old != next) {
                    old.recycle();
                }
            }
            View view = host;
            if (view != null) {
                view.postInvalidate();
            }
        }
    }
}
