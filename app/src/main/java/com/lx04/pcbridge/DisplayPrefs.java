package com.lx04.pcbridge;

import android.content.Context;
import android.content.SharedPreferences;

final class DisplayPrefs {
    private static final String PREFS = "lx04_bridge";
    private static final String KEY_UPSIDE_DOWN = "upside_down";
    private static final String KEY_LIGHT_THEME = "light_theme";

    private DisplayPrefs() {
    }

    static boolean isUpsideDown(Context context) {
        return prefs(context).getBoolean(KEY_UPSIDE_DOWN, false);
    }

    static void setUpsideDown(Context context, boolean upsideDown) {
        prefs(context).edit().putBoolean(KEY_UPSIDE_DOWN, upsideDown).apply();
    }

    static boolean isLightTheme(Context context) {
        return prefs(context).getBoolean(KEY_LIGHT_THEME, false);
    }

    static void setLightTheme(Context context, boolean lightTheme) {
        prefs(context).edit().putBoolean(KEY_LIGHT_THEME, lightTheme).apply();
    }

    private static SharedPreferences prefs(Context context) {
        return context.getApplicationContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }
}
