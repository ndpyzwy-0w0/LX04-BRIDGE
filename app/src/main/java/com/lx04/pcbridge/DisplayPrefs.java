package com.lx04.pcbridge;

import android.content.Context;
import android.content.SharedPreferences;

final class DisplayPrefs {
    private static final String PREFS = "lx04_bridge";
    private static final String KEY_UPSIDE_DOWN = "upside_down";
    private static final String KEY_SYS_ROTATION = "sys_rotation";
    private static final String KEY_UI_HIDDEN = "ui_hidden";
    private static final String KEY_LIGHT_THEME = "light_theme";
    private static final String KEY_HUD_STYLE = "hud_style";
    private static final String KEY_SCREEN_MIRROR = "screen_mirror";
    private static final String KEY_AUTO_HIDE_MUTE = "auto_hide_mute";
    private static final String KEY_BOOT_START = "boot_start";
    private static final String KEY_CLOCK_DATE = "clock_date";
    private static final String KEY_CLOCK_HOUR = "clock_hour";
    private static final String KEY_CLOCK_MINUTE = "clock_minute";
    private static final String KEY_CLOCK_SECOND = "clock_second";
    private static final String KEY_HUD_BG_SLOT = "hud_bg_slot";
    private static final String KEY_HUD_BG_ALPHA = "hud_bg_alpha";

    private DisplayPrefs() {
    }

    static boolean isUpsideDown(Context context) {
        return prefs(context).getBoolean(KEY_UPSIDE_DOWN, false);
    }

    static void setUpsideDown(Context context, boolean upsideDown) {
        prefs(context).edit().putBoolean(KEY_UPSIDE_DOWN, upsideDown).apply();
    }

    static int clampRotation(int rotation) {
        rotation = ((rotation % 4) + 4) % 4;
        return rotation >= 2 ? 2 : 0;
    }

    static int sysRotation(Context context) {
        return clampRotation(prefs(context).getInt(KEY_SYS_ROTATION, 0));
    }

    static void setSysRotation(Context context, int rotation) {
        prefs(context).edit().putInt(KEY_SYS_ROTATION, clampRotation(rotation)).apply();
    }

    static boolean isUiHidden(Context context) {
        return prefs(context).getBoolean(KEY_UI_HIDDEN, false);
    }

    static void setUiHidden(Context context, boolean hidden) {
        prefs(context).edit().putBoolean(KEY_UI_HIDDEN, hidden).apply();
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

    static boolean isAutoHideMute(Context context) {
        return prefs(context).getBoolean(KEY_AUTO_HIDE_MUTE, false);
    }

    static void setAutoHideMute(Context context, boolean on) {
        prefs(context).edit().putBoolean(KEY_AUTO_HIDE_MUTE, on).apply();
    }

    static boolean isBootStart(Context context) {
        return prefs(context).getBoolean(KEY_BOOT_START, false);
    }

    static void setBootStart(Context context, boolean on) {
        prefs(context).edit().putBoolean(KEY_BOOT_START, on).apply();
    }

    static boolean clockDate(Context context) {
        return prefs(context).getBoolean(KEY_CLOCK_DATE, true);
    }

    static void setClockDate(Context context, boolean on) {
        prefs(context).edit().putBoolean(KEY_CLOCK_DATE, on).apply();
    }

    static boolean clockHour(Context context) {
        return prefs(context).getBoolean(KEY_CLOCK_HOUR, true);
    }

    static void setClockHour(Context context, boolean on) {
        prefs(context).edit().putBoolean(KEY_CLOCK_HOUR, on).apply();
    }

    static boolean clockMinute(Context context) {
        return prefs(context).getBoolean(KEY_CLOCK_MINUTE, true);
    }

    static void setClockMinute(Context context, boolean on) {
        prefs(context).edit().putBoolean(KEY_CLOCK_MINUTE, on).apply();
    }

    static boolean clockSecond(Context context) {
        return prefs(context).getBoolean(KEY_CLOCK_SECOND, true);
    }

    static void setClockSecond(Context context, boolean on) {
        prefs(context).edit().putBoolean(KEY_CLOCK_SECOND, on).apply();
    }

    static int hudBgSlot(Context context) {
        return prefs(context).getInt(KEY_HUD_BG_SLOT, HudBackground.NONE);
    }

    static void setHudBgSlot(Context context, int slot) {
        prefs(context).edit().putInt(KEY_HUD_BG_SLOT, slot).apply();
    }

    static int hudBgAlpha(Context context) {
        return prefs(context).getInt(KEY_HUD_BG_ALPHA, HudBackground.DEFAULT_ALPHA);
    }

    static void setHudBgAlpha(Context context, int alpha) {
        prefs(context).edit().putInt(KEY_HUD_BG_ALPHA, alpha).apply();
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
