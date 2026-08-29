package com.lx04.pcbridge;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

public class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        if (context == null || intent == null || !isBootAction(intent.getAction())) {
            return;
        }
        if (!DisplayPrefs.isBootStart(context)) {
            return;
        }
        Intent launch = new Intent(context, MainActivity.class);
        launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_RESET_TASK_IF_NEEDED);
        try {
            context.startActivity(launch);
        } catch (RuntimeException ignored) {
        }
        if (!AudioCapture.hasMicPermission(context)) {
            return;
        }
        context.startForegroundService(new Intent(context, BridgeService.class));
    }

    private static boolean isBootAction(String action) {
        return Intent.ACTION_BOOT_COMPLETED.equals(action)
                || "android.intent.action.QUICKBOOT_POWERON".equals(action);
    }
}
