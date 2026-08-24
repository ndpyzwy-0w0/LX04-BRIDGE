package com.lx04.pcbridge;

import android.content.Context;
import android.content.pm.PackageInfo;

final class AppVersion {
    static String read(Context context) {
        try {
            PackageInfo info = context.getPackageManager().getPackageInfo(context.getPackageName(), 0);
            if (info.versionName != null && !info.versionName.isEmpty()) {
                return info.versionName;
            }
            return String.valueOf(info.versionCode);
        } catch (Exception e) {
            return "";
        }
    }

    static String label(String version) {
        if (version == null || version.isEmpty()) {
            return "v?";
        }
        return version.startsWith("v") || version.startsWith("V") ? version : "v" + version;
    }
}
