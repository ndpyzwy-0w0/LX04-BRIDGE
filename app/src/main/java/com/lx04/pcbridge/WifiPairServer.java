package com.lx04.pcbridge;

import android.content.Context;

import org.json.JSONObject;

import java.io.InputStream;
import java.io.OutputStream;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.NetworkInterface;
import java.net.Socket;
import java.net.SocketTimeoutException;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.Collections;
import java.util.Enumeration;
import java.util.Locale;

/**
 * 局域网（WiFi）配对与鉴权。
 *
 * <p>USB 模式走 adb forward，客户端地址必然是 127.0.0.1；WiFi 模式客户端带
 * 真实局域网地址，因此必须自己判断"这台上位机是否已被允许"，规则是：
 *
 * <ul>
 *   <li>回环地址：adb 转发的 USB 通道，永远放行（保持原有行为）。
 *   <li>其他地址：只有开启过配对（或配对模式正开着）才接受连接；并且 17890
 *       上必须先发一帧 {@code {"cmd":"wifi_auth", token|code}} 通过校验，
 *       17891/17892 只接受来自已授权/已配对 IP 的连接。
 * </ul>
 *
 * <p>配对码只显示在音箱屏幕上、由人工输入电脑，不随广播外发；配对成功后拿到
 * 的 token 存在本机与电脑上，之后重连不再需要配对码。
 */
final class WifiPairServer {
    interface Listener {
        void onWifiChanged();
    }

    static final int PORT = 17893;
    private static final String MAGIC = "LXB1";
    private static final int MAX_PACKET = 2048;
    private static final int MAX_ATTEMPTS = 5;
    private static final long COOLDOWN_MS = 30_000L;
    private static final long AUTH_WINDOW_MS = 6_000L;
    private static final long IP_CACHE_MS = 5_000L;

    static final WifiPairServer INSTANCE = new WifiPairServer();

    private final SecureRandom random = new SecureRandom();
    private final Object lock = new Object();

    private Context context;
    private Listener listener;
    private volatile boolean running;
    private DatagramSocket socket;
    private Thread thread;
    private volatile String pin = "";
    private volatile String authorizedIp = "";
    /** 本机局域网地址做缓存：设置页每帧都要显示它，不能每帧枚举网卡。 */
    private volatile String cachedIp = "";
    private long cachedIpAt;
    private volatile int attempts;
    private volatile long cooldownUntil;
    private volatile long pinAt;

    private WifiPairServer() {
    }

    void attach(Context context, Listener listener) {
        this.context = context.getApplicationContext();
        this.listener = listener;
    }

    // ---- 状态 -------------------------------------------------------------

    boolean pairing() {
        return context != null && DisplayPrefs.isWifiPairing(context);
    }

    /** 局域网是否允许接入：配对模式开着，或曾经配对成功过。 */
    boolean lanEnabled() {
        if (context == null) {
            return false;
        }
        return pairing() || !DisplayPrefs.wifiToken(context).isEmpty();
    }

    String pin() {
        return pin;
    }

    String pairedName() {
        return context == null ? "" : DisplayPrefs.wifiPairedName(context);
    }

    String pairedIp() {
        return context == null ? "" : DisplayPrefs.wifiPairedIp(context);
    }

    /** 是否已经和某台上位机配对成功过（有令牌）。 */
    boolean hasToken() {
        return context != null && !DisplayPrefs.wifiToken(context).isEmpty();
    }

    String localIp() {
        long now = System.currentTimeMillis();
        String cached = cachedIp;
        if (!cached.isEmpty() && now - cachedIpAt < IP_CACHE_MS) {
            return cached;
        }
        String found = scanLocalIp();
        cachedIp = found;
        cachedIpAt = now;
        return found;
    }

    private String scanLocalIp() {
        try {
            for (NetworkInterface nif : Collections.list(NetworkInterface.getNetworkInterfaces())) {
                if (!nif.isUp() || nif.isLoopback()) {
                    continue;
                }
                for (InetAddress addr : Collections.list(nif.getInetAddresses())) {
                    if (addr instanceof Inet4Address && !addr.isLoopbackAddress() && addr.isSiteLocalAddress()) {
                        return addr.getHostAddress();
                    }
                }
            }
            // 有些小爱固件把网卡标成非 site-local，再退一步取任意 IPv4。
            for (NetworkInterface nif : Collections.list(NetworkInterface.getNetworkInterfaces())) {
                if (!nif.isUp() || nif.isLoopback()) {
                    continue;
                }
                for (InetAddress addr : Collections.list(nif.getInetAddresses())) {
                    if (addr instanceof Inet4Address && !addr.isLoopbackAddress()) {
                        return addr.getHostAddress();
                    }
                }
            }
        } catch (Exception ignored) {
        }
        return "";
    }

    // ---- 开关 -------------------------------------------------------------

    synchronized void setPairing(boolean on) {
        if (context == null) {
            return;
        }
        DisplayPrefs.setWifiPairing(context, on);
        if (on) {
            rotatePin();
            start();
        } else {
            pin = "";
        }
        notifyChanged();
    }

    synchronized void forget() {
        if (context == null) {
            return;
        }
        DisplayPrefs.clearWifiPairing(context);
        pin = "";
        authorizedIp = "";
        notifyChanged();
    }

    private void rotatePin() {
        pin = String.format(Locale.US, "%06d", random.nextInt(1_000_000));
        pinAt = System.currentTimeMillis();
        attempts = 0;
        cooldownUntil = 0;
    }

    private void notifyChanged() {
        Listener current = listener;
        if (current != null) {
            try {
                current.onWifiChanged();
            } catch (Exception ignored) {
            }
        }
    }

    // ---- 生命周期 ---------------------------------------------------------

    void start() {
        if (running || context == null || !lanEnabled()) {
            return;
        }
        if (pairing() && pin.isEmpty()) {
            rotatePin();
        }
        synchronized (lock) {
            if (running) {
                return;
            }
            running = true;
            thread = new Thread(this::loop, "lx04-wifi-pair");
            thread.start();
        }
    }

    void stop() {
        running = false;
        DatagramSocket current = socket;
        socket = null;
        if (current != null) {
            try {
                current.close();
            } catch (Exception ignored) {
            }
        }
        Thread worker = thread;
        thread = null;
        if (worker != null) {
            worker.interrupt();
        }
    }

    /** 服务重启时按已保存的偏好恢复。 */
    void restore() {
        if (lanEnabled()) {
            if (pairing() && pin.isEmpty()) {
                rotatePin();
            }
            start();
        }
    }

    private void loop() {
        try {
            DatagramSocket sock = new DatagramSocket(null);
            sock.setReuseAddress(true);
            sock.bind(new InetSocketAddress(PORT));
            socket = sock;
            byte[] buffer = new byte[MAX_PACKET];
            while (running) {
                DatagramPacket packet = new DatagramPacket(buffer, buffer.length);
                try {
                    sock.receive(packet);
                } catch (SocketTimeoutException timeout) {
                    continue;
                } catch (Exception exc) {
                    if (!running) {
                        break;
                    }
                    continue;
                }
                handle(packet, sock);
            }
        } catch (Exception ignored) {
        } finally {
            running = false;
            socket = null;
        }
    }

    private void handle(DatagramPacket packet, DatagramSocket sock) {
        try {
            String text = new String(packet.getData(), packet.getOffset(), packet.getLength(),
                    StandardCharsets.UTF_8);
            JSONObject json = new JSONObject(text);
            if (!MAGIC.equals(json.optString("magic", ""))) {
                return;
            }
            String cmd = json.optString("cmd", "");
            String nonce = json.optString("nonce", "");
            if ("discover".equals(cmd)) {
                if (!lanEnabled()) {
                    return;
                }
                JSONObject offer = new JSONObject();
                offer.put("cmd", "offer");
                offer.put("magic", MAGIC);
                offer.put("nonce", nonce);
                offer.put("device", "LX04");
                offer.put("model", android.os.Build.MODEL);
                offer.put("android", android.os.Build.VERSION.RELEASE);
                offer.put("ip", localIp());
                offer.put("port", Protocol.PORT);
                offer.put("videoPort", Protocol.VIDEO_PORT);
                offer.put("toastPort", Protocol.TOAST_PORT);
                offer.put("pairing", pairing());
                offer.put("paired", !DisplayPrefs.wifiToken(context).isEmpty());
                send(sock, packet, offer.toString());
                return;
            }
            if ("pair".equals(cmd)) {
                handlePair(sock, packet, json, nonce);
            }
        } catch (Exception ignored) {
        }
    }

    private synchronized void handlePair(DatagramSocket sock, DatagramPacket packet, JSONObject json, String nonce) {
        String replyCmd;
        int left = 0;
        String token = "";
        if (!lanEnabled()) {
            replyCmd = "pair_deny";
        } else if (System.currentTimeMillis() < cooldownUntil) {
            replyCmd = "pair_deny";
        } else if (!pairing()) {
            replyCmd = "pair_deny";
        } else if ((token = pairWithCode(json.optString("code", ""), packet.getAddress(),
                json.optString("name", ""))) != null) {
            replyCmd = "pair_ok";
        } else {
            replyCmd = "pair_deny";
            left = Math.max(0, MAX_ATTEMPTS - attempts);
        }
        try {
            JSONObject reply = new JSONObject();
            reply.put("cmd", replyCmd);
            reply.put("magic", MAGIC);
            reply.put("nonce", nonce);
            if ("pair_ok".equals(replyCmd)) {
                reply.put("token", token);
                reply.put("ip", localIp());
            } else if (!lanEnabled() || !pairing()) {
                reply.put("reason", "off");
            } else if (System.currentTimeMillis() < cooldownUntil) {
                reply.put("reason", "cooldown");
                reply.put("left", 0);
            } else {
                reply.put("reason", "bad_code");
                reply.put("left", left);
            }
            send(sock, packet, reply.toString());
        } catch (Exception ignored) {
        }
    }

    private void send(DatagramSocket sock, DatagramPacket to, String text) {
        try {
            byte[] payload = text.getBytes(StandardCharsets.UTF_8);
            sock.send(new DatagramPacket(payload, payload.length, to.getAddress(), to.getPort()));
        } catch (Exception ignored) {
        }
    }

    /** 配对码校验与失败计数；UDP 线程和 TCP 鉴权线程都会调，必须串行化。 */
    private synchronized boolean checkCode(String code) {
        if (!pairing() || pin.isEmpty() || code == null
                || System.currentTimeMillis() < cooldownUntil) {
            return false;
        }
        if (System.currentTimeMillis() - pinAt > 30 * 60_000L) {
            return false;
        }
        if (!pin.equals(code.trim())) {
            attempts++;
            if (attempts >= MAX_ATTEMPTS) {
                cooldownUntil = System.currentTimeMillis() + COOLDOWN_MS;
                pin = "";
                notifyChanged();
            }
            return false;
        }
        return true;
    }

    private String newToken() {
        byte[] raw = new byte[16];
        random.nextBytes(raw);
        StringBuilder sb = new StringBuilder(raw.length * 2);
        for (byte b : raw) {
            sb.append(Character.forDigit((b >> 4) & 0xF, 16));
            sb.append(Character.forDigit(b & 0xF, 16));
        }
        return sb.toString();
    }

    // ---- TCP 鉴权 ---------------------------------------------------------

    /**
     * 17891 / 17892 的接入闸门：回环永远放行；局域网只放行已授权或已配对的 IP。
     */
    boolean acceptPeer(Socket socket) {
        InetAddress address = socket == null ? null : socket.getInetAddress();
        if (address == null || address.isLoopbackAddress()) {
            return true;
        }
        if (!lanEnabled()) {
            return false;
        }
        String ip = address.getHostAddress();
        return ip.equals(authorizedIp) || ip.equals(pairedIp());
    }

    /**
     * 17890 上的首帧鉴权。返回 true 表示放行，并在需要时把新 token 回给电脑。
     *
     * @param out 已经写过 HELLO，鉴权结果以 EVENT 帧回发
     * @return null 表示拒绝；否则返回本次连接使用的 token（可能为空串）
     */
    String authorize(Socket socket, InputStream in, OutputStream out) {
        InetAddress address = socket == null ? null : socket.getInetAddress();
        if (address != null && address.isLoopbackAddress()) {
            return "";
        }
        if (!lanEnabled()) {
            return null;
        }
        long deadline = System.currentTimeMillis() + AUTH_WINDOW_MS;
        try {
            socket.setSoTimeout((int) AUTH_WINDOW_MS);
        } catch (Exception ignored) {
        }
        try {
            while (System.currentTimeMillis() < deadline) {
                Protocol.Frame frame = Protocol.readFrame(in);
                if (frame == null) {
                    return null;
                }
                if (frame.type != Protocol.CONTROL || frame.payload == null || frame.payload.length == 0) {
                    continue;
                }
                JSONObject json = new JSONObject(new String(frame.payload, StandardCharsets.UTF_8));
                if (!"wifi_auth".equals(json.optString("cmd", ""))) {
                    continue;
                }
                String token = json.optString("token", "");
                String code = json.optString("code", "");
                String stored = DisplayPrefs.wifiToken(context);
                if (!token.isEmpty() && !stored.isEmpty() && token.equals(stored)) {
                    authorizedIp = address == null ? "" : address.getHostAddress();
                    replyAuth(out, true, "");
                    return token;
                }
                String fresh = pairWithCode(code, address, json.optString("name", ""));
                if (fresh != null) {
                    authorizedIp = address == null ? "" : address.getHostAddress();
                    replyAuth(out, true, fresh);
                    return fresh;
                }
                replyAuth(out, false, "");
                return null;
            }
        } catch (Exception ignored) {
        } finally {
            try {
                socket.setSoTimeout(15000);
            } catch (Exception ignored) {
            }
        }
        return null;
    }

    private synchronized String pairWithCode(String code, InetAddress address, String name) {
        if (code.isEmpty() || !checkCode(code)) {
            return null;
        }
        String fresh = newToken();
        DisplayPrefs.setWifiToken(context, fresh);
        if (address != null) {
            DisplayPrefs.setWifiPairedIp(context, address.getHostAddress());
        }
        DisplayPrefs.setWifiPairedName(context, name);
        DisplayPrefs.setWifiPairing(context, false);
        pin = "";
        attempts = 0;
        notifyChanged();
        return fresh;
    }

    private void replyAuth(OutputStream out, boolean ok, String token) {
        try {
            JSONObject reply = new JSONObject();
            reply.put("cmd", "wifi_auth");
            reply.put("ok", ok);
            if (ok && token != null && !token.isEmpty()) {
                reply.put("token", token);
            }
            byte[] payload = reply.toString().getBytes(StandardCharsets.UTF_8);
            byte[] frame = Protocol.encode(Protocol.EVENT, (byte) 0, 0,
                    android.os.SystemClock.elapsedRealtime(), payload);
            synchronized (out) {
                out.write(frame);
                out.flush();
            }
        } catch (Exception ignored) {
        }
    }
}
