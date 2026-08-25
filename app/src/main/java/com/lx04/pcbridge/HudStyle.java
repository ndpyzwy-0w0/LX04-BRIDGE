package com.lx04.pcbridge;

import android.graphics.Color;

import org.json.JSONArray;
import org.json.JSONObject;

final class HudStyle {
    static final String[] KEYS = {"cpu", "gpu", "ram", "disk"};
    static final String[] DEFAULT_METRICS = {"cpu", "gpu", "ram", "disk"};
    static final String[] DEFAULT_SUB_METRICS = {"cpuT", "gpuT", "ramGB", "diskGB"};
    static final String[] DEFAULT_TITLES = {"CPU", "GPU", "内存", "磁盘"};
    static final String[] PICK_METRICS = {
            "cpu", "cpuT", "gpu", "gpuT", "gpuW", "gpuFan", "vram",
            "ram", "ramGB", "disk", "diskGB", "diskIo", "netD", "netU", "cores", "gpuN"
    };
    static final int[] PALETTE = {
            0xFF8FA0BE, 0xFF5A6B84, 0xFF3DDC97, 0xFFFFB020, 0xFFFF5C7A, 0xFF6EA8FF,
            0xFFE8EEF8, 0xFFA78BFA, 0xFF22D3EE, 0xFFF472B6, 0xFFFBBF24, 0xFFFB923C
    };

    private final String[] titles = new String[] {"", "", "", ""};
    private final String[] metrics = new String[] {"", "", "", ""};
    private final String[] subMetrics = new String[] {"", "", "", ""};
    private final int[] titleColors = new int[4];
    private final int[] valueColors = new int[4];
    private long rev;

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
        if (json == null) {
            return;
        }
        long incoming = json.optLong("rev", 0);
        if (incoming > 0 && incoming < rev) {
            return;
        }
        if (json.optBoolean("reset", false)) {
            clear();
            if (incoming > 0) {
                rev = incoming;
            }
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
        if (incoming > 0) {
            rev = incoming;
        }
    }

    synchronized JSONObject toStatusJson() {
        JSONObject o = new JSONObject();
        try {
            o.put("rev", rev);
            if (isClear()) {
                o.put("reset", true);
                return o;
            }
            o.put("reset", false);
            JSONArray cards = new JSONArray();
            for (int i = 0; i < 4; i++) {
                JSONObject card = new JSONObject();
                card.put("key", KEYS[i]);
                card.put("title", title(i, DEFAULT_TITLES[i]));
                card.put("metric", metric(i));
                card.put("subMetric", subMetric(i));
                if (titleColors[i] != 0) {
                    card.put("titleColor", hex(titleColors[i]));
                }
                if (valueColors[i] != 0) {
                    card.put("valueColor", hex(valueColors[i]));
                }
                cards.put(card);
            }
            o.put("cards", cards);
        } catch (Exception ignored) {
        }
        return o;
    }

    synchronized JSONObject toStoreJson() {
        return toStatusJson();
    }

    synchronized boolean isClear() {
        for (int i = 0; i < 4; i++) {
            if (!titles[i].isEmpty() || !metrics[i].isEmpty() || !subMetrics[i].isEmpty()
                    || titleColors[i] != 0 || valueColors[i] != 0) {
                return false;
            }
        }
        return true;
    }

    synchronized long rev() {
        return rev;
    }

    synchronized void bumpRev() {
        long now = System.currentTimeMillis();
        rev = Math.max(rev + 1, now);
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

    synchronized String rawTitle(int index) {
        if (index < 0 || index >= 4) {
            return "";
        }
        return titles[index];
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

    synchronized void setMetric(int index, String metric) {
        if (index < 0 || index >= 4 || !isPickable(metric)) {
            return;
        }
        if (isDefaultTitle(metric(index), titles[index])) {
            titles[index] = "";
        }
        metrics[index] = metric;
        bumpRev();
    }

    synchronized void setSubMetric(int index, String metric) {
        if (index < 0 || index >= 4 || !isKnown(metric)) {
            return;
        }
        subMetrics[index] = metric;
        bumpRev();
    }

    synchronized void setTitleColor(int index, int color) {
        if (index < 0 || index >= 4) {
            return;
        }
        titleColors[index] = color;
        bumpRev();
    }

    synchronized void setValueColor(int index, int color) {
        if (index < 0 || index >= 4) {
            return;
        }
        valueColors[index] = color;
        bumpRev();
    }

    synchronized void resetSlot(int index) {
        if (index < 0 || index >= 4) {
            return;
        }
        titles[index] = "";
        metrics[index] = "";
        subMetrics[index] = "";
        titleColors[index] = 0;
        valueColors[index] = 0;
        bumpRev();
    }

    static boolean isPickable(String metric) {
        return isKnown(metric) && !"none".equals(metric);
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

    static String metricLabel(String metric) {
        if ("none".equals(metric)) {
            return "不显示";
        }
        if ("cpu".equals(metric)) {
            return "CPU 占用";
        }
        if ("cpuT".equals(metric)) {
            return "CPU 温度";
        }
        if ("gpu".equals(metric)) {
            return "GPU 占用";
        }
        if ("gpuT".equals(metric)) {
            return "GPU 温度";
        }
        if ("gpuW".equals(metric)) {
            return "GPU 功耗";
        }
        if ("gpuFan".equals(metric)) {
            return "GPU 风扇";
        }
        if ("vram".equals(metric)) {
            return "显存占用";
        }
        if ("ram".equals(metric)) {
            return "内存占用";
        }
        if ("ramGB".equals(metric)) {
            return "内存容量";
        }
        if ("disk".equals(metric)) {
            return "磁盘占用";
        }
        if ("diskGB".equals(metric)) {
            return "磁盘容量";
        }
        if ("diskIo".equals(metric)) {
            return "磁盘 IO";
        }
        if ("netD".equals(metric)) {
            return "下载速度";
        }
        if ("netU".equals(metric)) {
            return "上传速度";
        }
        if ("cores".equals(metric)) {
            return "CPU 核数";
        }
        if ("gpuN".equals(metric)) {
            return "显卡型号";
        }
        return metric;
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

    static String hex(int color) {
        return String.format("#%06X", color & 0xFFFFFF);
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
