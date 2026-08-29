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
    private final byte[] decodeScratch = new byte[32 * 1024];
    private Bitmap shown;
    private Bitmap scratch;
    private long frameAt;
    private byte[] pending;
    private Thread decoder;
    private volatile boolean running;
    private volatile int epoch;
    private volatile View host;

    private ScreenMirror() {
        options.inPreferredConfig = Bitmap.Config.RGB_565;
        options.inDither = false;
        options.inScaled = false;
        options.inMutable = true;
        options.inTempStorage = decodeScratch;
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
            if (!BridgeService.STATE.screenMirror) {
                return;
            }
            pending = jpeg;
            inLock.notify();
        }
        startDecoder();
    }

    void clear() {
        // Drop refs only. recycle() races the hardware render thread and leftover JPEG decodes.
        synchronized (inLock) {
            epoch++;
            pending = null;
            inLock.notifyAll();
        }
        synchronized (lock) {
            shown = null;
            scratch = null;
            frameAt = 0;
        }
    }

    boolean hasFrame() {
        synchronized (lock) {
            return shown != null && !shown.isRecycled();
        }
    }

    boolean stale() {
        synchronized (lock) {
            return frameAt != 0 && SystemClock.elapsedRealtime() - frameAt > 1500;
        }
    }

    void draw(Canvas canvas, int w, int h) {
        synchronized (lock) {
            if (shown == null || shown.isRecycled()) {
                return;
            }
            dest.set(0, 0, w, h);
            boolean scale = shown.getWidth() != w || shown.getHeight() != h;
            paint.setFilterBitmap(scale);
            canvas.drawBitmap(shown, null, dest, paint);
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
            int myEpoch;
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
                myEpoch = epoch;
            }
            if (!running || jpeg == null) {
                continue;
            }
            Bitmap reuse;
            synchronized (lock) {
                if (myEpoch != epoch) {
                    continue;
                }
                reuse = scratch;
            }
            options.inBitmap = (reuse != null && !reuse.isRecycled() && reuse.isMutable()) ? reuse : null;
            Bitmap decoded = decode(jpeg);
            if (decoded == null && options.inBitmap != null) {
                options.inBitmap = null;
                decoded = decode(jpeg);
            }
            if (decoded == null) {
                continue;
            }
            synchronized (lock) {
                if (myEpoch != epoch) {
                    continue;
                }
                Bitmap oldShown = shown;
                shown = decoded;
                scratch = (oldShown != null && oldShown != decoded) ? oldShown : null;
                frameAt = SystemClock.elapsedRealtime();
            }
            View view = host;
            if (view != null) {
                view.postInvalidateOnAnimation();
            }
        }
    }

    private Bitmap decode(byte[] jpeg) {
        try {
            return BitmapFactory.decodeByteArray(jpeg, 0, jpeg.length, options);
        } catch (RuntimeException e) {
            return null;
        }
    }
}
