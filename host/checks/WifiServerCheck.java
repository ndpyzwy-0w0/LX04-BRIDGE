package com.lx04.pcbridge;

import android.content.Context;
import org.json.JSONObject;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.lang.reflect.Field;
import java.net.InetAddress;
import java.net.Socket;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.BooleanSupplier;

/** Executes production protocol/auth/server code; only platform services are stubbed. */
public class WifiServerCheck {
    static void require(boolean value, String message) {
        if (!value) throw new AssertionError(message);
    }

    static void set(Object object, String name, Object value) throws Exception {
        Field field = object.getClass().getDeclaredField(name);
        field.setAccessible(true);
        field.set(object, value);
    }

    static void await(BooleanSupplier condition) throws Exception {
        long deadline = System.nanoTime() + 3_000_000_000L;
        while (!condition.getAsBoolean()) {
            require(System.nanoTime() < deadline, "Timed out waiting for server");
            Thread.sleep(10);
        }
    }

    static class AuthSocket extends Socket {
        @Override public InetAddress getInetAddress() {
            try { return InetAddress.getByName("192.168.1.10"); }
            catch (Exception e) { throw new AssertionError(e); }
        }
        @Override public void setSoTimeout(int timeout) { }
    }

    static String auth(WifiPairServer wifi, String key, String secret) throws Exception {
        JSONObject json = new JSONObject().put("cmd", "wifi_auth").put(key, secret);
        byte[] frame = Protocol.encode(Protocol.CONTROL, (byte) 0, 0, 0,
                json.toString().getBytes("UTF-8"));
        return wifi.authorize(new AuthSocket(), new ByteArrayInputStream(frame),
                new ByteArrayOutputStream());
    }

    static void enableCode(WifiPairServer wifi) throws Exception {
        DisplayPrefs.pairing = true;
        set(wifi, "pin", "123456");
        set(wifi, "pinAt", System.currentTimeMillis());
        set(wifi, "cooldownUntil", 0L);
    }

    static void checkPairing() throws Exception {
        WifiPairServer wifi = WifiPairServer.INSTANCE;
        wifi.attach(new Context(), null);
        DisplayPrefs.token = "existing-token";
        enableCode(wifi);
        DisplayPrefs.pairing = false; // A leftover PIN must not bypass the switch.
        require(auth(wifi, "code", "123456") == null, "Closed pairing accepted old PIN");
        require("existing-token".equals(DisplayPrefs.token), "Old PIN replaced token");
        require("existing-token".equals(auth(wifi, "token", "existing-token")),
                "Stored token must still reconnect when pairing is off");
        enableCode(wifi);
        wifi.setPairing(false);
        require(wifi.pin().isEmpty(), "Switching pairing off must erase PIN");
        enableCode(wifi);
        String token = auth(wifi, "code", "123456");
        require(token != null && token.length() == 32, "Open pairing must issue token");
        require(!wifi.pairing() && wifi.pin().isEmpty(), "Successful pairing must erase PIN");
        require(auth(wifi, "code", "123456") == null, "PIN was reused after success");
        require(token.equals(DisplayPrefs.token), "Reused PIN overwrote valid token");
        require(token.equals(auth(wifi, "token", token)), "New token must reconnect");
        enableCode(wifi);
        set(wifi, "cooldownUntil", System.currentTimeMillis() + 30_000L);
        require(auth(wifi, "code", "123456") == null, "TCP ignored cooldown");
        wifi.forget();
        require(wifi.pin().isEmpty() && !wifi.lanEnabled(), "Forget must erase PIN and token");
        require(auth(wifi, "token", token) == null, "Forgotten token still accepted");
    }

    static Socket connect(String ip, byte credential) throws Exception {
        Socket socket = new Socket(ip, Protocol.PORT);
        socket.setSoTimeout(3000);
        require(Protocol.readFrame(socket.getInputStream()).type == Protocol.HELLO,
                "Expected HELLO");
        socket.getOutputStream().write(credential);
        socket.getOutputStream().flush();
        return socket;
    }

    static void checkSessions(String ip) throws Exception {
        require(!InetAddress.getByName(ip).isLoopbackAddress(), "Use this PC's LAN address");
        AtomicInteger connected = new AtomicInteger();
        AtomicInteger disconnected = new AtomicInteger();
        AtomicInteger rejected = new AtomicInteger();
        BridgeState state = new BridgeState();
        TcpBridgeServer server = new TcpBridgeServer(state, new TcpBridgeServer.Callbacks() {
            public void prepareForClient() { }
            public void onClient(boolean on, String name) {
                state.clientConnected = on;
                if (on) connected.incrementAndGet(); else disconnected.incrementAndGet();
            }
            public void onControl(JSONObject json) { }
            public void onPlay(byte[] pcm, boolean muted) { }
            public void onFile(int slot, byte[] jpeg) { }
            public boolean authorize(Socket socket, java.io.InputStream in,
                    java.io.OutputStream out) {
                try {
                    if (in.read() == 'A') return true;
                } catch (Exception ignored) { }
                rejected.incrementAndGet();
                return false;
            }
        });
        Socket current = null;
        Socket replacement = null;
        server.start();
        try {
            Field bound = TcpBridgeServer.class.getDeclaredField("server");
            bound.setAccessible(true);
            await(() -> { try { return bound.get(server) != null; }
                          catch (Exception e) { throw new AssertionError(e); } });
            current = connect(ip, (byte) 'A');
            await(() -> connected.get() == 1);
            try (Socket denied = connect(ip, (byte) 'X')) {
                require(denied.getInputStream().read() == -1, "Denied peer must close");
            }
            await(() -> rejected.get() == 1);
            Thread.sleep(50);
            require(disconnected.get() == 0 && state.clientConnected && state.clientIsLan,
                    "Rejected peer changed the active session");
            replacement = connect(ip, (byte) 'A');
            await(() -> connected.get() == 2);
            Thread.sleep(100);
            require(disconnected.get() == 0 && state.clientConnected,
                    "Superseded peer disconnected its replacement");
            replacement.close();
            await(() -> disconnected.get() == 1);
            require(!state.clientConnected, "Current peer disconnect was not reported");
            Thread.sleep(50);
            require(disconnected.get() == 1, "Disconnect callback must run only once");
        } finally {
            if (current != null) current.close();
            if (replacement != null) replacement.close();
            server.stop();
        }
    }

    public static void main(String[] args) throws Exception {
        checkPairing();
        checkSessions(args[0]);
        System.out.println("Pairing authorization and session ownership: all checks passed");
    }
}

// Platform persistence/audio/HUD stand-ins; protocol/auth/server implementations are real.
class DisplayPrefs {
    static boolean pairing;
    static String token = "", ip = "", name = "";
    static boolean isWifiPairing(Context c) { return pairing; }
    static void setWifiPairing(Context c, boolean v) { pairing = v; }
    static String wifiToken(Context c) { return token; }
    static void setWifiToken(Context c, String v) { token = v; }
    static String wifiPairedIp(Context c) { return ip; }
    static void setWifiPairedIp(Context c, String v) { ip = v; }
    static String wifiPairedName(Context c) { return name; }
    static void setWifiPairedName(Context c, String v) { name = v; }
    static void clearWifiPairing(Context c) { pairing = false; token = ip = name = ""; }
}
class BridgeState {
    volatile boolean clientConnected, clientIsLan, flushStatus;
    boolean usbConnected, usbAdb, recording, micMuted, spkMuted, lightTheme;
    boolean uiHidden, screenMirror, toastOverlay, wifiOn, wifiPairing, wifiPaired;
    String wifiIp = "", wifiPairCode = "", audioSource = "", apkVersion = "";
    int sampleRate = 48000, channels = 1, sysRotation;
    long dropped, frames;
    float level, playLevel;
    HudStyle hudStyle = new HudStyle();
}
class HudStyle { JSONObject toStatusJson() { return new JSONObject(); } }
class BridgeService { static float musicVolume() { return 1f; } }
class HudBackground {
    static final HudBackground INSTANCE = new HudBackground();
    static final int SLOTS = 3;
    int selected() { return -1; }
    int alpha() { return 100; }
    boolean used(int slot) { return false; }
}
