package com.lx04.pcbridge;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.view.WindowManager;

public class MainActivity extends Activity {
    private StatusHudView hud;
    private boolean appliedUpsideDown;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Runnable tick = new Runnable() {
        @Override
        public void run() {
            if (hud != null) {
                boolean want = BridgeService.STATE.upsideDown;
                if (want != appliedUpsideDown) {
                    applyDisplayRotation(want);
                }
                hud.invalidate();
            }
            handler.postDelayed(this, 50);
        }
    };

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
        });
        setContentView(hud);
        BridgeService.STATE.upsideDown = DisplayPrefs.isUpsideDown(this);
        applyDisplayRotation(BridgeService.STATE.upsideDown);
        hideSystemUi();
        ensurePermissionAndStart();
    }

    @Override
    protected void onResume() {
        super.onResume();
        hideSystemUi();
        handler.post(tick);
    }

    @Override
    protected void onPause() {
        handler.removeCallbacks(tick);
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
