package com.lx04.pcbridge;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.os.SystemClock;

final class Watchdog {
    static final String ACTION = "com.lx04.pcbridge.WATCHDOG";
    private static final long INTERVAL_MS = 45_000L;

    private Watchdog() {
    }

    static void schedule(Context context) {
        AlarmManager am = (AlarmManager) context.getSystemService(Context.ALARM_SERVICE);
        if (am == null) {
            return;
        }
        PendingIntent pi = pending(context);
        am.cancel(pi);
        am.setExactAndAllowWhileIdle(
                AlarmManager.ELAPSED_REALTIME_WAKEUP,
                SystemClock.elapsedRealtime() + INTERVAL_MS,
                pi);
    }

    static void startService(Context context) {
        if (!AudioCapture.hasMicPermission(context)) {
            return;
        }
        context.startForegroundService(new Intent(context, BridgeService.class));
    }

    private static PendingIntent pending(Context context) {
        Intent intent = new Intent(context, WatchdogReceiver.class);
        intent.setAction(ACTION);
        return PendingIntent.getBroadcast(
                context,
                7,
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }
}
