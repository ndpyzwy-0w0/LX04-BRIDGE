package com.lx04.pcbridge;

final class SparkHistory {
    static final int LEN = 48;
    static final String[] KEYS = {
            "cpu", "cpuT", "gpu", "gpuT", "gpuW", "gpuFan", "vram",
            "ram", "ramGB", "disk", "diskGB", "diskIo", "netD", "netU"
    };

    private final float[][] rings = new float[KEYS.length][LEN];
    private int head;
    private int count;
    private long lastAt;

    SparkHistory() {
        clear();
    }

    synchronized void clear() {
        head = 0;
        count = 0;
        lastAt = 0;
        for (float[] row : rings) {
            java.util.Arrays.fill(row, Float.NaN);
        }
    }

    synchronized void record(BridgeState s) {
        if (s == null || s.pcStatsAt == 0 || s.pcStatsAt == lastAt) {
            return;
        }
        lastAt = s.pcStatsAt;
        for (int i = 0; i < KEYS.length; i++) {
            rings[i][head] = value(s, KEYS[i]);
        }
        head = (head + 1) % LEN;
        if (count < LEN) {
            count++;
        }
    }

    synchronized int copy(String metric, float[] dest) {
        int index = indexOf(metric);
        if (index < 0 || count <= 0 || dest == null || dest.length == 0) {
            return 0;
        }
        int n = Math.min(count, dest.length);
        int start = (head - n + LEN) % LEN;
        for (int i = 0; i < n; i++) {
            dest[i] = rings[index][(start + i) % LEN];
        }
        return n;
    }

    static boolean percentScale(String metric) {
        return "cpu".equals(metric) || "gpu".equals(metric) || "gpuFan".equals(metric)
                || "vram".equals(metric) || "ram".equals(metric) || "disk".equals(metric)
                || "diskIo".equals(metric);
    }

    static boolean tempScale(String metric) {
        return "cpuT".equals(metric) || "gpuT".equals(metric);
    }

    private static float value(BridgeState s, String metric) {
        if ("cpu".equals(metric)) {
            return s.pcCpu;
        }
        if ("cpuT".equals(metric)) {
            return s.pcCpuTemp;
        }
        if ("gpu".equals(metric)) {
            return s.pcGpu;
        }
        if ("gpuT".equals(metric)) {
            return s.pcGpuTemp;
        }
        if ("gpuW".equals(metric)) {
            return s.pcGpuWatts;
        }
        if ("gpuFan".equals(metric)) {
            return s.pcGpuFan;
        }
        if ("vram".equals(metric)) {
            return s.pcVram;
        }
        if ("ram".equals(metric)) {
            return s.pcRam;
        }
        if ("ramGB".equals(metric)) {
            return s.pcRamUsed;
        }
        if ("disk".equals(metric)) {
            return s.pcDisk;
        }
        if ("diskGB".equals(metric)) {
            return s.pcDiskUsed;
        }
        if ("diskIo".equals(metric)) {
            return s.pcDiskIo;
        }
        if ("netD".equals(metric)) {
            return s.pcNetDown;
        }
        if ("netU".equals(metric)) {
            return s.pcNetUp;
        }
        return Float.NaN;
    }

    private static int indexOf(String metric) {
        for (int i = 0; i < KEYS.length; i++) {
            if (KEYS[i].equals(metric)) {
                return i;
            }
        }
        return -1;
    }
}
