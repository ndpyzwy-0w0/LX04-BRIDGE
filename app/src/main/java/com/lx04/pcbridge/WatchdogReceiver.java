package com.lx04.pcbridge;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

public class WatchdogReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        Watchdog.startService(context);
        Watchdog.schedule(context);
    }
}
