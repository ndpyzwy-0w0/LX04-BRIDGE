package com.lx04.pcbridge;

import android.graphics.Color;

import org.json.JSONArray;
import org.json.JSONObject;

final class HudStyle {
    static final String[] KEYS = {"cpu", "gpu", "ram", "disk"};
    static final String[] DEFAULT_TITLES = {"CPU", "GPU", "内存", "D:"};

    private final String[] titles = new String[] {"", "", "", ""};
    private final int[] titleColors = new int[4];
    private final int[] valueColors = new int[4];

    synchronized void clear() {
        for (int i = 0; i < 4; i++) {
            titles[i] = "";
            titleColors[i] = 0;
            valueColors[i] = 0;
        }
    }

    synchronized void applyJson(JSONObject json) {
        if (json == null || json.optBoolean("reset", false)) {
            clear();
            return;
        }
        JSONArray cards = json.optJSONArray("cards");
        if (cards == null) {
            return;
        }
        clear();
        int count = Math.min(cards.length(), 4);
        for (int i = 0; i < count; i++) {
            JSONObject card = cards.optJSONObject(i);
            if (card == null) {
                continue;
            }
            int index = indexOf(card.optString("key", ""));
            if (index < 0) {
                index = i;
            }
            titles[index] = card.optString("title", "");
            titleColors[index] = parseColor(card.optString("titleColor", ""));
            valueColors[index] = parseColor(card.optString("valueColor", ""));
        }
    }

    synchronized String title(int index, String fallback) {
        if (index < 0 || index >= 4) {
            return fallback;
        }
        String custom = titles[index];
        if (custom == null || custom.isEmpty()) {
            return fallback;
        }
        if (DEFAULT_TITLES[index].equals(custom)) {
            return fallback;
        }
        return custom;
    }

    synchronized int titleColor(int index) {
        if (index < 0 || index >= 4) {
            return 0;
        }
        return titleColors[index];
    }

    synchronized int valueColor(int index) {
        if (index < 0 || index >= 4) {
            return 0;
        }
        return valueColors[index];
    }

    private static int indexOf(String key) {
        for (int i = 0; i < KEYS.length; i++) {
            if (KEYS[i].equals(key)) {
                return i;
            }
        }
        return -1;
    }

    static int parseColor(String hex) {
        if (hex == null || hex.isEmpty()) {
            return 0;
        }
        try {
            return Color.parseColor(hex);
        } catch (Exception ignored) {
            return 0;
        }
    }
}
