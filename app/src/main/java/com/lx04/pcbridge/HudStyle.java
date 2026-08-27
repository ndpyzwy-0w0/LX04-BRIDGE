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
    static final String[] CHART_METRICS = {
            "cpu", "cpuT", "gpu", "gpuT", "gpuW", "gpuFan", "vram",
            "ram", "ramGB", "disk", "diskGB", "diskIo", "netD", "netU"
    };
    static final String CHART_FOLLOW = "main";
    static final int MAX_SUBS = 4;
    static final int[] PALETTE = {
            0xFF8FA0BE, 0xFF5A6B84, 0xFF3DDC97, 0xFFFFB020, 0xFFFF5C7A, 0xFF6EA8FF,
            0xFFE8EEF8, 0xFFA78BFA, 0xFF22D3EE, 0xFFF472B6, 0xFFFBBF24, 0xFFFB923C
    };

    private final String[] titles = new String[] {"", "", "", ""};
    private final String[] metrics = new String[] {"", "", "", ""};
    private final String[][] subLines = new String[4][MAX_SUBS];
    private final int[] subCounts = new int[4];
    private final String[] chartMetrics = new String[] {"", "", "", ""};
    private final boolean[] chartOn = new boolean[] {true, true, true, true};
    static final int DEFAULT_VALUE_SIZE = 28;
    static final int DEFAULT_SUB_SIZE = 11;
    static final int MIN_VALUE_SIZE = 12;
    static final int MAX_VALUE_SIZE = 56;
    static final int MIN_SUB_SIZE = 8;
    static final int MAX_SUB_SIZE = 28;

    private final int[] titleColors = new int[4];
    private final int[] valueColors = new int[4];
    private final int[] valueSizes = new int[4];
    private final int[] subSizes = new int[4];
    private long rev;

    synchronized void clear() {
        for (int i = 0; i < 4; i++) {
            titles[i] = "";
            metrics[i] = "";
            clearSubs(i);
            chartMetrics[i] = "";
            chartOn[i] = true;
            titleColors[i] = 0;
            valueColors[i] = 0;
            valueSizes[i] = 0;
            subSizes[i] = 0;
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
            applySubJson(index, card);
            chartMetrics[index] = normalizeChartMetric(card.optString("chartMetric", ""));
            chartOn[index] = !card.has("chart") || card.optBoolean("chart", true);
            titleColors[index] = parseColor(card.optString("titleColor", ""));
            valueColors[index] = parseColor(card.optString("valueColor", ""));
            valueSizes[index] = normalizeValueSize(card.optInt("valueSize", 0));
            subSizes[index] = normalizeSubSize(card.optInt("subSize", 0));
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
                putSubJson(card, i);
                if (titleColors[i] != 0) {
                    card.put("titleColor", hex(titleColors[i]));
                }
                if (valueColors[i] != 0) {
                    card.put("valueColor", hex(valueColors[i]));
                }
                if (valueSize(i) != DEFAULT_VALUE_SIZE) {
                    card.put("valueSize", valueSize(i));
                }
                if (subSize(i) != DEFAULT_SUB_SIZE) {
                    card.put("subSize", subSize(i));
                }
                if (!chartOn[i]) {
                    card.put("chart", false);
                }
                if (!chartMetrics[i].isEmpty()) {
                    card.put("chartMetric", chartMetrics[i]);
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
            if (!titles[i].isEmpty() || !metrics[i].isEmpty() || subCounts[i] > 0
                    || !chartMetrics[i].isEmpty() || !chartOn[i]
                    || titleColors[i] != 0 || valueColors[i] != 0
                    || valueSizes[i] != 0 || subSizes[i] != 0) {
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
        String[] shown = displaySubs(index);
        if (shown.length == 0) {
            return "none";
        }
        return shown[0];
    }

    synchronized String[] displaySubs(int index) {
        if (index < 0 || index >= 4) {
            return new String[0];
        }
        if (subCounts[index] <= 0) {
            return new String[] { DEFAULT_SUB_METRICS[index] };
        }
        int n = 0;
        String[] tmp = new String[subCounts[index]];
        for (int i = 0; i < subCounts[index]; i++) {
            String key = subLines[index][i];
            if (isKnown(key) && !"none".equals(key)) {
                tmp[n++] = key;
            }
        }
        String[] out = new String[n];
        System.arraycopy(tmp, 0, out, 0, n);
        return out;
    }

    synchronized int editorSubCount(int index) {
        if (index < 0 || index >= 4) {
            return 1;
        }
        return subCounts[index] <= 0 ? 1 : subCounts[index];
    }

    synchronized String editorSubAt(int index, int line) {
        if (index < 0 || index >= 4) {
            return "none";
        }
        if (subCounts[index] <= 0) {
            return line == 0 ? DEFAULT_SUB_METRICS[index] : "none";
        }
        if (line < 0 || line >= subCounts[index]) {
            return "none";
        }
        String key = subLines[index][line];
        return isKnown(key) ? key : "none";
    }

    synchronized boolean canAddSub(int index) {
        return editorSubCount(index) < MAX_SUBS;
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

    synchronized int valueSize(int index) {
        if (index < 0 || index >= 4 || valueSizes[index] == 0) {
            return DEFAULT_VALUE_SIZE;
        }
        return clamp(valueSizes[index], MIN_VALUE_SIZE, MAX_VALUE_SIZE);
    }

    synchronized int subSize(int index) {
        if (index < 0 || index >= 4 || subSizes[index] == 0) {
            return DEFAULT_SUB_SIZE;
        }
        return clamp(subSizes[index], MIN_SUB_SIZE, MAX_SUB_SIZE);
    }

    synchronized boolean chartOn(int index) {
        if (index < 0 || index >= 4) {
            return true;
        }
        return chartOn[index];
    }

    synchronized String rawChartMetric(int index) {
        if (index < 0 || index >= 4) {
            return "";
        }
        return chartMetrics[index];
    }

    synchronized String chartMetric(int index) {
        String custom = rawChartMetric(index);
        if (isChartable(custom)) {
            return custom;
        }
        String main = metric(index);
        return isChartable(main) ? main : "cpu";
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
        setSubMetricAt(index, 0, metric);
    }

    synchronized void setSubMetricAt(int index, int line, String metric) {
        if (index < 0 || index >= 4 || !isKnown(metric)) {
            return;
        }
        ensureStoredSubs(index);
        if (line < 0 || line >= subCounts[index]) {
            return;
        }
        if (metric.equals(subLines[index][line])) {
            return;
        }
        subLines[index][line] = metric;
        bumpRev();
    }

    synchronized boolean addSubMetric(int index) {
        if (index < 0 || index >= 4) {
            return false;
        }
        ensureStoredSubs(index);
        if (subCounts[index] >= MAX_SUBS) {
            return false;
        }
        subLines[index][subCounts[index]] = unusedSub(index);
        subCounts[index]++;
        bumpRev();
        return true;
    }

    synchronized void removeSubMetric(int index, int line) {
        if (index < 0 || index >= 4) {
            return;
        }
        ensureStoredSubs(index);
        if (line < 0 || line >= subCounts[index]) {
            return;
        }
        if (subCounts[index] == 1) {
            if ("none".equals(subLines[index][0])) {
                return;
            }
            subLines[index][0] = "none";
            bumpRev();
            return;
        }
        for (int i = line; i < subCounts[index] - 1; i++) {
            subLines[index][i] = subLines[index][i + 1];
        }
        subLines[index][subCounts[index] - 1] = "";
        subCounts[index]--;
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

    synchronized void setValueSize(int index, int size) {
        if (index < 0 || index >= 4) {
            return;
        }
        int stored = normalizeValueSize(size);
        if (valueSizes[index] == stored) {
            return;
        }
        valueSizes[index] = stored;
        bumpRev();
    }

    synchronized void setSubSize(int index, int size) {
        if (index < 0 || index >= 4) {
            return;
        }
        int stored = normalizeSubSize(size);
        if (subSizes[index] == stored) {
            return;
        }
        subSizes[index] = stored;
        bumpRev();
    }

    synchronized void setChartOn(int index, boolean on) {
        if (index < 0 || index >= 4 || chartOn[index] == on) {
            return;
        }
        chartOn[index] = on;
        bumpRev();
    }

    synchronized void setChartMetric(int index, String metric) {
        if (index < 0 || index >= 4) {
            return;
        }
        String stored = "";
        if (metric != null && !metric.isEmpty() && !CHART_FOLLOW.equals(metric) && isChartable(metric)) {
            stored = metric;
        }
        if (stored.equals(chartMetrics[index])) {
            return;
        }
        chartMetrics[index] = stored;
        bumpRev();
    }

    synchronized void resetSlot(int index) {
        if (index < 0 || index >= 4) {
            return;
        }
        titles[index] = "";
        metrics[index] = "";
        clearSubs(index);
        chartMetrics[index] = "";
        chartOn[index] = true;
        titleColors[index] = 0;
        valueColors[index] = 0;
        valueSizes[index] = 0;
        subSizes[index] = 0;
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

    static boolean isChartable(String metric) {
        if (metric == null || metric.isEmpty() || "none".equals(metric)
                || "cores".equals(metric) || "gpuN".equals(metric)) {
            return false;
        }
        return isKnown(metric);
    }

    static String metricLabel(String metric) {
        if (CHART_FOLLOW.equals(metric)) {
            return "跟随大字";
        }
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

    static int clamp(int value, int min, int max) {
        return Math.max(min, Math.min(max, value));
    }

    static int normalizeValueSize(int size) {
        if (size <= 0 || size == DEFAULT_VALUE_SIZE) {
            return 0;
        }
        return clamp(size, MIN_VALUE_SIZE, MAX_VALUE_SIZE);
    }

    static int normalizeSubSize(int size) {
        if (size <= 0 || size == DEFAULT_SUB_SIZE) {
            return 0;
        }
        return clamp(size, MIN_SUB_SIZE, MAX_SUB_SIZE);
    }

    static String normalizeChartMetric(String metric) {
        if (metric == null || metric.isEmpty() || CHART_FOLLOW.equals(metric) || !isChartable(metric)) {
            return "";
        }
        return metric;
    }

    private void clearSubs(int index) {
        subCounts[index] = 0;
        for (int i = 0; i < MAX_SUBS; i++) {
            subLines[index][i] = "";
        }
    }

    private void ensureStoredSubs(int index) {
        if (subCounts[index] > 0) {
            return;
        }
        subLines[index][0] = DEFAULT_SUB_METRICS[index];
        subCounts[index] = 1;
    }

    private String unusedSub(int index) {
        for (int p = 0; p < PICK_METRICS.length; p++) {
            String key = PICK_METRICS[p];
            boolean used = false;
            for (int i = 0; i < subCounts[index]; i++) {
                if (key.equals(subLines[index][i])) {
                    used = true;
                    break;
                }
            }
            if (!used) {
                return key;
            }
        }
        return PICK_METRICS[0];
    }

    private void applySubJson(int index, JSONObject card) {
        clearSubs(index);
        JSONArray extra = card.optJSONArray("subMetrics");
        if (extra != null && extra.length() > 0) {
            int n = 0;
            int len = Math.min(extra.length(), MAX_SUBS);
            for (int i = 0; i < len; i++) {
                String key = extra.optString(i, "");
                if (!isKnown(key)) {
                    continue;
                }
                subLines[index][n++] = key;
            }
            subCounts[index] = n;
            return;
        }
        String one = card.optString("subMetric", "");
        if (isKnown(one)) {
            subLines[index][0] = one;
            subCounts[index] = 1;
        }
    }

    private void putSubJson(JSONObject card, int index) throws Exception {
        card.put("subMetric", subMetric(index));
        if (subCounts[index] <= 0) {
            return;
        }
        JSONArray arr = new JSONArray();
        for (int i = 0; i < subCounts[index]; i++) {
            arr.put(subLines[index][i]);
        }
        card.put("subMetrics", arr);
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
