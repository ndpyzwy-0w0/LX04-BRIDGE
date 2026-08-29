package com.lx04.pcbridge;

import android.media.AudioAttributes;
import android.media.AudioFormat;
import android.media.AudioManager;
import android.media.AudioTrack;
import android.os.Process;

import java.util.concurrent.ArrayBlockingQueue;

final class AudioPlayback {
    private final ArrayBlockingQueue<byte[]> queue = new ArrayBlockingQueue<>(4);
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
        int channelMask = AudioFormat.CHANNEL_OUT_STEREO;
        int min = AudioTrack.getMinBufferSize(rate, channelMask, AudioFormat.ENCODING_PCM_16BIT);
        if (min <= 0) {
            return;
        }
        AudioFormat format = new AudioFormat.Builder()
                .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                .setSampleRate(rate)
                .setChannelMask(channelMask)
                .build();
        track = openTrack(format, min, true);
        if (track == null) {
            track = openTrack(format, min, false);
        }
        if (track == null) {
            try {
                track = new AudioTrack(AudioManager.STREAM_MUSIC, rate, channelMask,
                        AudioFormat.ENCODING_PCM_16BIT, min, AudioTrack.MODE_STREAM);
                if (track.getState() != AudioTrack.STATE_INITIALIZED) {
                    track.release();
                    track = null;
                    return;
                }
            } catch (Exception e) {
                track = null;
                return;
            }
        }
        try {
            track.play();
        } catch (Exception e) {
            track.release();
            track = null;
            return;
        }
        running = true;
        thread = new Thread(this::loop, "lx04-spk");
        thread.start();
    }

    private static AudioTrack openTrack(AudioFormat format, int buffer, boolean lowLatency) {
        try {
            AudioAttributes attrs = new AudioAttributes.Builder()
                    .setUsage(lowLatency ? AudioAttributes.USAGE_GAME : AudioAttributes.USAGE_MEDIA)
                    .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
                    .build();
            AudioTrack.Builder builder = new AudioTrack.Builder()
                    .setAudioAttributes(attrs)
                    .setAudioFormat(format)
                    .setBufferSizeInBytes(buffer)
                    .setTransferMode(AudioTrack.MODE_STREAM);
            if (lowLatency) {
                builder.setPerformanceMode(AudioTrack.PERFORMANCE_MODE_LOW_LATENCY);
            }
            AudioTrack t = builder.build();
            if (t.getState() != AudioTrack.STATE_INITIALIZED) {
                t.release();
                return null;
            }
            return t;
        } catch (Exception e) {
            return null;
        }
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
        if (muted || BridgeService.STATE.volume <= 0.001f) {
            java.util.Arrays.fill(pcm, (byte) 0);
            peak = 0f;
        }
        if (!queue.offer(pcm)) {
            queue.poll();
            queue.offer(pcm);
        }
    }

    private void loop() {
        Process.setThreadPriority(Process.THREAD_PRIORITY_URGENT_AUDIO);
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
