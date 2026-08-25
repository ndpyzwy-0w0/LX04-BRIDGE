package com.lx04.pcbridge;

import android.content.Context;
import android.content.SharedPreferences;

final class DisplayPrefs {
    private static final String PREFS = "lx04_bridge";
    private static final String KEY_UPSIDE_DOWN = "upside_down";

    private DisplayPrefs() {
    }

    static boolean isUpsideDown(Context context) {
        return prefs(context).getBoolean(KEY_UPSIDE_DOWN, false);
    }

    static void setUpsideDown(Context context, boolean upsideDown) {
        prefs(context).edit().putBoolean(KEY_UPSIDE_DOWN, upsideDown).apply();
    }

    private static SharedPreferences prefs(Context context) {
        return context.getApplicationContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }
}
