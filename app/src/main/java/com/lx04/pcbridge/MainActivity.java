package com.lx04.pcbridge;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.ActivityInfo;
import android.content.pm.PackageManager;
import android.content.res.Configuration;
import android.graphics.drawable.ColorDrawable;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.KeyEvent;
import android.view.View;
import android.view.WindowManager;

public class MainActivity extends Activity {
    private static volatile MainActivity foreground;
    private StatusHudView hud;
    private boolean appliedUpsideDown;
    private int appliedSysRotation = Integer.MIN_VALUE;
    private boolean appliedLightTheme;
    private boolean allowLeave;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Runnable tick = new Runnable() {
        @Override
        public void run() {
            if (hud != null) {
                boolean want = BridgeService.STATE.upsideDown;
                if (want != appliedUpsideDown) {
                    applyDisplayRotation(want);
                }
                int rot = BridgeService.STATE.sysRotation;
                if (rot != appliedSysRotation) {
                    applySysRotation(rot);
                }
                boolean light = BridgeService.STATE.lightTheme;
                if (light != appliedLightTheme) {
                    applyChromeColors(light);
                }
                hud.invalidate();
            }
            long delay = (BridgeService.STATE.screenMirror || BridgeService.STATE.toastOverlay) ? 16 : 50;
            handler.postDelayed(this, delay);
        }
    };

    static void refreshHud() {
        MainActivity activity = foreground;
        if (activity == null) {
            return;
        }
        StatusHudView view = activity.hud;
        if (view == null) {
            return;
        }
        view.postInvalidate();
        activity.handler.removeCallbacks(activity.tick);
        activity.handler.post(activity.tick);
    }

    static void applySysRotation() {
        MainActivity activity = foreground;
        if (activity == null) {
            return;
        }
        activity.handler.post(() -> activity.applySysRotation(BridgeService.STATE.sysRotation));
    }

    static void hideUi() {
        MainActivity activity = foreground;
        if (activity == null) {
            return;
        }
        activity.handler.post(activity::leaveToBackground);
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON
                | WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED);
        BridgeService.STATE.apkVersion = AppVersion.read(this);
        hud = new StatusHudView(this);
        hud.setListener(new StatusHudView.Listener() {
            @Override
            public void onMicMuteTap() {
                BridgeService.toggleMicMute();
            }

            @Override
            public void onSpkMuteTap() {
                BridgeService.toggleSpkMute();
            }

            @Override
            public void onResetStyleTap() {
                BridgeService.resetHudStyle(MainActivity.this);
            }

            @Override
            public void onHudStyleChanged() {
                BridgeService.persistHudStyle(MainActivity.this);
            }

            @Override
            public void onPointer(float x, float y, String act) {
                BridgeService.sendPointer(x, y, act);
            }

            @Override
            public void onToastAction(String id, String label) {
                BridgeService.sendToastAction(id, label);
            }

            @Override
            public void onToastDismiss() {
                BridgeService.sendToastDismiss();
            }
        });
        setContentView(hud);
        BridgeService.STATE.upsideDown = DisplayPrefs.isUpsideDown(this);
        BridgeService.STATE.lightTheme = DisplayPrefs.isLightTheme(this);
        BridgeService.STATE.sysRotation = DisplayPrefs.sysRotation(this);
        if (BridgeService.STATE.uiHidden || DisplayPrefs.isUiHidden(this)) {
            BridgeService.STATE.uiHidden = false;
            DisplayPrefs.setUiHidden(this, false);
            BridgeService.STATE.flushStatus = true;
        }
        BridgeService.STATE.screenMirror = DisplayPrefs.isScreenMirror(this);
        BridgeService.STATE.autoHideMute = DisplayPrefs.isAutoHideMute(this);
        BridgeService.STATE.bootStart = DisplayPrefs.isBootStart(this);
        BridgeService.loadClockPrefs(this);
        DisplayPrefs.loadHudStyle(this, BridgeService.STATE.hudStyle);
        HudBackground.INSTANCE.init(this);
        applyDisplayRotation(BridgeService.STATE.upsideDown);
        applySysRotation(BridgeService.STATE.sysRotation);
        applyChromeColors(BridgeService.STATE.lightTheme);
        hideSystemUi();
        ensurePermissionAndStart();
    }

    @Override
    protected void onResume() {
        super.onResume();
        foreground = this;
        hideSystemUi();
        handler.post(tick);
    }

    @Override
    protected void onPause() {
        handler.removeCallbacks(tick);
        if (foreground == this) {
            foreground = null;
        }
        super.onPause();
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) {
            hideSystemUi();
        }
    }

    @Override
    public void onConfigurationChanged(Configuration newConfig) {
        super.onConfigurationChanged(newConfig);
        hideSystemUi();
        if (hud != null) {
            hud.requestLayout();
            hud.invalidate();
        }
    }

    @Override
    public boolean dispatchKeyEvent(KeyEvent event) {
        if (event.getKeyCode() == KeyEvent.KEYCODE_BACK) {
            if (event.getAction() == KeyEvent.ACTION_UP && event.getRepeatCount() == 0
                    && !event.isCanceled()) {
                consumeSystemExit();
            }
            return true;
        }
        return super.dispatchKeyEvent(event);
    }

    @Override
    public void onBackPressed() {
        consumeSystemExit();
    }

    @Override
    public boolean moveTaskToBack(boolean nonRoot) {
        if (allowLeave) {
            return super.moveTaskToBack(nonRoot);
        }
        consumeSystemExit();
        return true;
    }

    @Override
    public void finish() {
        if (allowLeave) {
            super.finish();
            return;
        }
        consumeSystemExit();
    }

    private void leaveToBackground() {
        allowLeave = true;
        finish();
    }

    private void consumeSystemExit() {
        if (hud != null) {
            hud.handleBack();
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        if (requestCode == 11) {
            ensurePermissionAndStart();
        }
    }

    private void ensurePermissionAndStart() {
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            BridgeService.STATE.permissionDenied = true;
            BridgeService.STATE.headline = "需要麦克风权限";
            BridgeService.STATE.detail = "请授权录音后继续";
            requestPermissions(new String[] {Manifest.permission.RECORD_AUDIO}, 11);
            return;
        }
        BridgeService.STATE.permissionDenied = false;
        Intent service = new Intent(this, BridgeService.class);
        startForegroundService(service);
    }

    private void applyDisplayRotation(boolean upsideDown) {
        appliedUpsideDown = upsideDown;
        hud.post(() -> {
            hud.setPivotX(hud.getWidth() / 2f);
            hud.setPivotY(hud.getHeight() / 2f);
            hud.setRotation(upsideDown ? 180f : 0f);
        });
    }

    private static final int[] SYS_ORIENTATIONS = {
            ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE,
            ActivityInfo.SCREEN_ORIENTATION_PORTRAIT,
            ActivityInfo.SCREEN_ORIENTATION_REVERSE_LANDSCAPE,
            ActivityInfo.SCREEN_ORIENTATION_REVERSE_PORTRAIT
    };

    private void applySysRotation(int rotation) {
        rotation = DisplayPrefs.clampRotation(rotation);
        appliedSysRotation = rotation;
        setRequestedOrientation(SYS_ORIENTATIONS[rotation]);
    }

    private void applyChromeColors(boolean lightTheme) {
        appliedLightTheme = lightTheme;
        int color = StatusHudView.windowColor(lightTheme);
        getWindow().setBackgroundDrawable(new ColorDrawable(color));
        getWindow().setStatusBarColor(color);
        getWindow().setNavigationBarColor(color);
    }

    private void hideSystemUi() {
        View decor = getWindow().getDecorView();
        decor.setSystemUiVisibility(View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                | View.SYSTEM_UI_FLAG_FULLSCREEN
                | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                | View.SYSTEM_UI_FLAG_LAYOUT_STABLE);
    }
}
