package com.lx04.pcbridge;

import android.media.AudioFormat;
import android.media.AudioManager;
import android.media.AudioTrack;
import android.os.Process;

import java.util.concurrent.ArrayBlockingQueue;

final class AudioPlayback {
    private final ArrayBlockingQueue<byte[]> queue = new ArrayBlockingQueue<>(24);
    private volatile boolean running;
    private Thread thread;
    private AudioTrack track;
    private volatile float peak;

    float getPeak() {
        return peak;
    }

    synchronized void start() {
        if (running && track != null) {
            return;
        }
        stop();
        int rate = 48000;
        int channels = AudioFormat.CHANNEL_OUT_STEREO;
        int min = AudioTrack.getMinBufferSize(rate, channels, AudioFormat.ENCODING_PCM_16BIT);
        if (min <= 0) {
            return;
        }
        int buffer = Math.max(min, rate / 25 * 4);
        try {
            track = new AudioTrack(AudioManager.STREAM_MUSIC, rate, channels,
                    AudioFormat.ENCODING_PCM_16BIT, buffer, AudioTrack.MODE_STREAM);
            if (track.getState() != AudioTrack.STATE_INITIALIZED) {
                track.release();
                track = null;
                return;
            }
            track.play();
        } catch (Exception e) {
            if (track != null) {
                track.release();
                track = null;
            }
            return;
        }
        running = true;
        thread = new Thread(this::loop, "lx04-spk");
        thread.start();
    }

    synchronized void stop() {
        running = false;
        queue.clear();
        if (thread != null) {
            thread.interrupt();
            try {
                thread.join(400);
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
            }
            thread = null;
        }
        if (track != null) {
            try {
                track.stop();
            } catch (Exception ignored) {
            }
            track.release();
            track = null;
        }
        peak = 0f;
    }

    void push(byte[] pcm, boolean muted) {
        if (!running || pcm == null || pcm.length == 0) {
            return;
        }
        byte[] copy = pcm.clone();
        if (muted || BridgeService.STATE.volume <= 0.001f) {
            java.util.Arrays.fill(copy, (byte) 0);
            peak = 0f;
        }
        if (!queue.offer(copy)) {
            queue.poll();
            queue.offer(copy);
        }
    }

    private void loop() {
        Process.setThreadPriority(Process.THREAD_PRIORITY_AUDIO);
        AudioTrack t = track;
        if (t == null) {
            return;
        }
        while (running) {
            byte[] pcm;
            try {
                pcm = queue.take();
            } catch (InterruptedException e) {
                break;
            }
            peak = peak(pcm);
            try {
                t.write(pcm, 0, pcm.length);
            } catch (Exception e) {
                break;
            }
        }
    }

    private static float peak(byte[] pcm) {
        int max = 0;
        for (int i = 0; i + 1 < pcm.length; i += 2) {
            int sample = (pcm[i] & 0xFF) | (pcm[i + 1] << 8);
            if (sample > 32767) {
                sample -= 65536;
            }
            int abs = sample < 0 ? -sample : sample;
            if (abs > max) {
                max = abs;
            }
        }
        return max / 32768f;
    }
}
