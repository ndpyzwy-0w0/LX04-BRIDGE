package com.lx04.pcbridge;

import android.graphics.Color;

import org.json.JSONArray;
import org.json.JSONObject;

final class HudStyle {
    static final String[] KEYS = {"cpu", "gpu", "ram", "disk"};
    static final String[] DEFAULT_METRICS = {"cpu", "gpu", "ram", "disk"};
    static final String[] DEFAULT_SUB_METRICS = {"cpuT", "gpuT", "ramGB", "diskGB"};
    static final String[] DEFAULT_TITLES = {"CPU", "GPU", "内存", "磁盘"};

    private final String[] titles = new String[] {"", "", "", ""};
    private final String[] metrics = new String[] {"", "", "", ""};
    private final String[] subMetrics = new String[] {"", "", "", ""};
    private final int[] titleColors = new int[4];
    private final int[] valueColors = new int[4];

    synchronized void clear() {
        for (int i = 0; i < 4; i++) {
            titles[i] = "";
            metrics[i] = "";
            subMetrics[i] = "";
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
            metrics[index] = card.optString("metric", "");
            subMetrics[index] = card.optString("subMetric", "");
            titleColors[index] = parseColor(card.optString("titleColor", ""));
            valueColors[index] = parseColor(card.optString("valueColor", ""));
        }
    }

    synchronized String metric(int index) {
        if (index < 0 || index >= 4) {
            return "cpu";
        }
        String custom = metrics[index];
        if (isKnown(custom)) {
            return custom;
        }
        return DEFAULT_METRICS[index];
    }

    synchronized String subMetric(int index) {
        if (index < 0 || index >= 4) {
            return DEFAULT_SUB_METRICS[0];
        }
        String custom = subMetrics[index];
        if (isKnown(custom)) {
            return custom;
        }
        return DEFAULT_SUB_METRICS[index];
    }

    synchronized String title(int index, String fallback) {
        if (index < 0 || index >= 4) {
            return fallback;
        }
        String custom = titles[index];
        String metric = metric(index);
        if (custom != null && !custom.isEmpty()) {
            if (isDefaultTitle(metric, custom)) {
                return fallback;
            }
            return custom;
        }
        return fallback;
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

    static boolean isKnown(String metric) {
        return "cpu".equals(metric) || "cpuT".equals(metric)
                || "gpu".equals(metric) || "gpuT".equals(metric)
                || "gpuW".equals(metric) || "gpuFan".equals(metric) || "vram".equals(metric)
                || "ram".equals(metric) || "ramGB".equals(metric)
                || "disk".equals(metric) || "diskGB".equals(metric) || "diskIo".equals(metric)
                || "netD".equals(metric) || "netU".equals(metric)
                || "cores".equals(metric) || "gpuN".equals(metric) || "none".equals(metric);
    }

    static boolean isDefaultTitle(String metric, String title) {
        if (title == null || title.isEmpty()) {
            return true;
        }
        if (("disk".equals(metric) || "diskGB".equals(metric)) && ("D:".equals(title) || "磁盘".equals(title))) {
            return true;
        }
        return fallbackTitle(metric, "").equals(title);
    }

    static String fallbackTitle(String metric, String diskName) {
        if ("disk".equals(metric) || "diskGB".equals(metric)) {
            if (diskName != null && !diskName.isEmpty()) {
                return diskName;
            }
            return "磁盘";
        }
        if ("cpu".equals(metric) || "cpuT".equals(metric)) {
            return "CPU";
        }
        if ("gpu".equals(metric) || "gpuT".equals(metric)) {
            return "GPU";
        }
        if ("gpuW".equals(metric)) {
            return "功耗";
        }
        if ("gpuFan".equals(metric)) {
            return "风扇";
        }
        if ("vram".equals(metric)) {
            return "显存";
        }
        if ("ram".equals(metric) || "ramGB".equals(metric)) {
            return "内存";
        }
        if ("diskIo".equals(metric)) {
            return "IO";
        }
        if ("netD".equals(metric)) {
            return "下载";
        }
        if ("netU".equals(metric)) {
            return "上传";
        }
        if ("cores".equals(metric)) {
            return "核数";
        }
        if ("gpuN".equals(metric)) {
            return "显卡";
        }
        return "CPU";
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
