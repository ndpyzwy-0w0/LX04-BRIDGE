package com.lx04.pcbridge;

import android.content.Context;
import android.content.SharedPreferences;

final class DisplayPrefs {
    private static final String PREFS = "lx04_bridge";
    private static final String KEY_UPSIDE_DOWN = "upside_down";
    private static final String KEY_LIGHT_THEME = "light_theme";
    private static final String KEY_HUD_STYLE = "hud_style";
    private static final String KEY_SCREEN_MIRROR = "screen_mirror";

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

    static boolean isScreenMirror(Context context) {
        return prefs(context).getBoolean(KEY_SCREEN_MIRROR, false);
    }

    static void setScreenMirror(Context context, boolean on) {
        prefs(context).edit().putBoolean(KEY_SCREEN_MIRROR, on).apply();
    }

    static String hudStyleJson(Context context) {
        return prefs(context).getString(KEY_HUD_STYLE, "");
    }

    static void setHudStyleJson(Context context, String json) {
        prefs(context).edit().putString(KEY_HUD_STYLE, json == null ? "" : json).apply();
    }

    static void clearHudStyle(Context context) {
        prefs(context).edit().remove(KEY_HUD_STYLE).apply();
    }

    static void loadHudStyle(Context context, HudStyle style) {
        String raw = hudStyleJson(context);
        if (raw == null || raw.isEmpty() || style == null) {
            if (style != null) {
                style.clear();
            }
            return;
        }
        try {
            style.applyJson(new org.json.JSONObject(raw));
        } catch (Exception ignored) {
            style.clear();
        }
    }

    private static SharedPreferences prefs(Context context) {
        return context.getApplicationContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }
}
