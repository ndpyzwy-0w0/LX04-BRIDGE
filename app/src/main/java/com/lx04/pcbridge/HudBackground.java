package com.lx04.pcbridge;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Rect;
import android.graphics.RectF;

import java.io.File;
import java.io.FileOutputStream;

final class HudBackground {
    static final HudBackground INSTANCE = new HudBackground();
    static final int SLOTS = 3;
    static final int NONE = -1;
    static final int MIN_ALPHA = 20;
    static final int MAX_ALPHA = 100;
    static final int DEFAULT_ALPHA = 100;

    private final Bitmap[] bitmaps = new Bitmap[SLOTS];
    private final boolean[] used = new boolean[SLOTS];
    private final Paint paint = new Paint(Paint.FILTER_BITMAP_FLAG);
    private final Rect src = new Rect();
    private final RectF dst = new RectF();
    private final BitmapFactory.Options bounds = new BitmapFactory.Options();
    private final BitmapFactory.Options decode = new BitmapFactory.Options();
    private Context app;
    private int selected = NONE;
    private int alpha = DEFAULT_ALPHA;

    private HudBackground() {
        bounds.inJustDecodeBounds = true;
        bounds.inScaled = false;
        decode.inPreferredConfig = Bitmap.Config.RGB_565;
        decode.inDither = false;
        decode.inScaled = false;
        decode.inMutable = false;
    }

    synchronized void init(Context context) {
        if (context == null) {
            return;
        }
        app = context.getApplicationContext();
        selected = DisplayPrefs.hudBgSlot(app);
        alpha = clampAlpha(DisplayPrefs.hudBgAlpha(app));
        for (int i = 0; i < SLOTS; i++) {
            loadSlot(i);
        }
        if (selected < NONE || selected >= SLOTS || (selected >= 0 && !used[selected])) {
            selected = NONE;
        }
    }

    synchronized boolean put(Context context, int slot, byte[] jpeg) {
        remember(context);
        if (app == null || slot < 0 || slot >= SLOTS || jpeg == null || jpeg.length < 24) {
            return false;
        }
        if ((jpeg[0] & 0xFF) != 0xFF || (jpeg[1] & 0xFF) != 0xD8) {
            return false;
        }
        Bitmap next = decodeJpeg(jpeg);
        if (next == null) {
            return false;
        }
        if (!writeSlot(slot, jpeg)) {
            recycle(next);
            return false;
        }
        recycle(bitmaps[slot]);
        bitmaps[slot] = next;
        used[slot] = true;
        selected = slot;
        persist();
        return true;
    }

    synchronized void select(Context context, int slot) {
        remember(context);
        if (slot == NONE) {
            selected = NONE;
            persist();
            return;
        }
        if (slot < 0 || slot >= SLOTS || !used[slot]) {
            return;
        }
        selected = slot;
        persist();
    }

    synchronized void delete(Context context, int slot) {
        remember(context);
        if (app == null || slot < 0 || slot >= SLOTS) {
            return;
        }
        File file = slotFile(slot);
        if (file != null) {
            //noinspection ResultOfMethodCallIgnored
            file.delete();
        }
        recycle(bitmaps[slot]);
        bitmaps[slot] = null;
        used[slot] = false;
        if (selected == slot) {
            selected = NONE;
        }
        persist();
    }

    synchronized void setAlpha(Context context, int value) {
        remember(context);
        int next = clampAlpha(value);
        if (alpha == next) {
            return;
        }
        alpha = next;
        persist();
    }

    synchronized int selected() {
        return selected;
    }

    synchronized boolean used(int slot) {
        return slot >= 0 && slot < SLOTS && used[slot];
    }

    synchronized int alpha() {
        return alpha;
    }

    int alpha255() {
        return Math.round(alpha() * 255f / 100f);
    }

    synchronized boolean hasImage() {
        return current() != null;
    }

    synchronized void draw(Canvas canvas, int w, int h) {
        Bitmap bmp = current();
        if (bmp == null) {
            return;
        }
        coverDest(bmp.getWidth(), bmp.getHeight(), w, h, dst);
        src.set(0, 0, bmp.getWidth(), bmp.getHeight());
        canvas.drawBitmap(bmp, src, dst, paint);
    }

    synchronized boolean drawThumbnail(Canvas canvas, int slot, RectF dest) {
        if (slot < 0 || slot >= SLOTS || !used[slot]) {
            return false;
        }
        Bitmap bmp = bitmaps[slot];
        if (bmp == null || bmp.isRecycled()) {
            return false;
        }
        coverDest(bmp.getWidth(), bmp.getHeight(), dest.width(), dest.height(), dst);
        dst.offset(dest.left, dest.top);
        src.set(0, 0, bmp.getWidth(), bmp.getHeight());
        canvas.save();
        canvas.clipRect(dest);
        canvas.drawBitmap(bmp, src, dst, paint);
        canvas.restore();
        return true;
    }

    private Bitmap current() {
        if (selected < 0 || selected >= SLOTS || !used[selected]) {
            return null;
        }
        Bitmap bmp = bitmaps[selected];
        if (bmp == null || bmp.isRecycled()) {
            return null;
        }
        return bmp;
    }

    private void loadSlot(int slot) {
        File file = slotFile(slot);
        if (file == null || !file.isFile() || file.length() < 24) {
            used[slot] = false;
            recycle(bitmaps[slot]);
            bitmaps[slot] = null;
            return;
        }
        Bitmap bmp = BitmapFactory.decodeFile(file.getAbsolutePath(), decodeOptions());
        if (bmp == null) {
            used[slot] = false;
            recycle(bitmaps[slot]);
            bitmaps[slot] = null;
            return;
        }
        recycle(bitmaps[slot]);
        bitmaps[slot] = bmp;
        used[slot] = true;
    }

    private boolean writeSlot(int slot, byte[] jpeg) {
        File file = slotFile(slot);
        if (file == null) {
            return false;
        }
        File parent = file.getParentFile();
        if (parent != null && !parent.exists() && !parent.mkdirs()) {
            return false;
        }
        File tmp = new File(file.getAbsolutePath() + ".tmp");
        FileOutputStream out = null;
        try {
            out = new FileOutputStream(tmp);
            out.write(jpeg);
            out.flush();
            out.close();
            out = null;
            if (file.exists() && !file.delete()) {
                //noinspection ResultOfMethodCallIgnored
                tmp.delete();
                return false;
            }
            if (!tmp.renameTo(file)) {
                //noinspection ResultOfMethodCallIgnored
                tmp.delete();
                return false;
            }
            return true;
        } catch (Exception e) {
            if (tmp.exists()) {
                //noinspection ResultOfMethodCallIgnored
                tmp.delete();
            }
            return false;
        } finally {
            if (out != null) {
                try {
                    out.close();
                } catch (Exception ignored) {
                }
            }
        }
    }

    private File slotFile(int slot) {
        if (app == null || slot < 0 || slot >= SLOTS) {
            return null;
        }
        return new File(app.getFilesDir(), "hudbg_" + slot + ".jpg");
    }

    private Bitmap decodeJpeg(byte[] jpeg) {
        bounds.inJustDecodeBounds = true;
        BitmapFactory.decodeByteArray(jpeg, 0, jpeg.length, bounds);
        int w = bounds.outWidth;
        int h = bounds.outHeight;
        if (w <= 0 || h <= 0) {
            return null;
        }
        int sample = 1;
        while (w / sample > 1600 || h / sample > 960) {
            sample *= 2;
        }
        BitmapFactory.Options options = decodeOptions();
        options.inSampleSize = sample;
        return BitmapFactory.decodeByteArray(jpeg, 0, jpeg.length, options);
    }

    private BitmapFactory.Options decodeOptions() {
        BitmapFactory.Options options = new BitmapFactory.Options();
        options.inPreferredConfig = Bitmap.Config.RGB_565;
        options.inDither = false;
        options.inScaled = false;
        options.inMutable = false;
        return options;
    }

    private void persist() {
        if (app == null) {
            return;
        }
        DisplayPrefs.setHudBgSlot(app, selected);
        DisplayPrefs.setHudBgAlpha(app, alpha);
        BridgeService.STATE.flushStatus = true;
    }

    private void remember(Context context) {
        if (app == null && context != null) {
            init(context);
        }
    }

    private static void coverDest(int bw, int bh, float dw, float dh, RectF dest) {
        if (bw <= 0 || bh <= 0 || dw <= 0 || dh <= 0) {
            dest.set(0, 0, dw, dh);
            return;
        }
        float scale = Math.max(dw / bw, dh / bh);
        float w = bw * scale;
        float h = bh * scale;
        dest.set((dw - w) / 2f, (dh - h) / 2f, (dw + w) / 2f, (dh + h) / 2f);
    }

    static int clampAlpha(int value) {
        return Math.max(MIN_ALPHA, Math.min(MAX_ALPHA, value));
    }

    private static void recycle(Bitmap bitmap) {
        if (bitmap != null && !bitmap.isRecycled()) {
            bitmap.recycle();
        }
    }
}
