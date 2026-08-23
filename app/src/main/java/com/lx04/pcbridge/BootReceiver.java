package com.lx04.pcbridge;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

public class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        if (intent == null || !Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())) {
            return;
        }
        if (!AudioCapture.hasMicPermission(context)) {
            return;
        }
        Intent service = new Intent(context, BridgeService.class);
        context.startForegroundService(service);
    }
}
