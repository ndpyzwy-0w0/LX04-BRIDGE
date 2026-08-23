package com.lx04.pcbridge;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.provider.Settings;

final class UsbMonitor {
    interface Listener {
        void onUsbChanged(boolean connected, boolean adb);
    }

    private final Context context;
    private final Listener listener;
    private final BroadcastReceiver receiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            dispatch(intent);
        }
    };

    UsbMonitor(Context context, Listener listener) {
        this.context = context.getApplicationContext();
        this.listener = listener;
    }

    void start() {
        IntentFilter filter = new IntentFilter("android.hardware.usb.action.USB_STATE");
        Intent sticky = context.registerReceiver(receiver, filter);
        dispatch(sticky);
    }

    void stop() {
        try {
            context.unregisterReceiver(receiver);
        } catch (Exception ignored) {
        }
    }

    private void dispatch(Intent intent) {
        boolean connected = false;
        boolean adb = false;
        if (intent != null) {
            connected = intent.getBooleanExtra("connected", false);
            adb = intent.getBooleanExtra("adb", false);
        }
        try {
            adb = adb || Settings.Global.getInt(context.getContentResolver(),
                    Settings.Global.ADB_ENABLED, 0) == 1;
        } catch (Exception ignored) {
        }
        listener.onUsbChanged(connected, adb);
    }
}
