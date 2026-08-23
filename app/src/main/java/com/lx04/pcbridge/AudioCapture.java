package com.lx04.pcbridge;

import android.content.Context;
import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.MediaRecorder;
import android.os.Process;

final class AudioCapture {
    interface Listener {
        void onAudio(byte[] pcm, int length, float peak);
    }

    private final Listener listener;
    private volatile boolean running;
    private Thread thread;
    private AudioRecord record;
    private int sampleRate = 48000;
    private int channels = 1;

    AudioCapture(Listener listener) {
        this.listener = listener;
    }

    int getSampleRate() {
        return sampleRate;
    }

    int getChannels() {
        return channels;
    }

    synchronized boolean start() {
        stop();
        int[] rates = new int[] {48000, 44100, 16000};
        int[] sources = new int[] {
                MediaRecorder.AudioSource.VOICE_RECOGNITION,
                MediaRecorder.AudioSource.MIC,
                MediaRecorder.AudioSource.CAMCORDER
        };
        for (int source : sources) {
            for (int rate : rates) {
                record = tryOpen(source, rate, AudioFormat.CHANNEL_IN_MONO);
                if (record != null) {
                    sampleRate = rate;
                    channels = 1;
                    running = true;
                    thread = new Thread(this::loop, "lx04-mic");
                    thread.start();
                    return true;
                }
            }
        }
        return false;
    }

    synchronized void stop() {
        running = false;
        if (thread != null) {
            thread.interrupt();
            try {
                thread.join(400);
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
            }
            thread = null;
        }
        if (record != null) {
            try {
                record.stop();
            } catch (Exception ignored) {
            }
            record.release();
            record = null;
        }
    }

    private AudioRecord tryOpen(int source, int rate, int channelMask) {
        int min = AudioRecord.getMinBufferSize(rate, channelMask, AudioFormat.ENCODING_PCM_16BIT);
        if (min <= 0) {
            return null;
        }
        int buffer = Math.max(min, rate / 50 * 2 * 8);
        try {
            AudioRecord rec = new AudioRecord(source, rate, channelMask,
                    AudioFormat.ENCODING_PCM_16BIT, buffer);
            if (rec.getState() != AudioRecord.STATE_INITIALIZED) {
                rec.release();
                return null;
            }
            rec.startRecording();
            if (rec.getRecordingState() != AudioRecord.RECORDSTATE_RECORDING) {
                rec.release();
                return null;
            }
            return rec;
        } catch (Exception e) {
            return null;
        }
    }

    private void loop() {
        Process.setThreadPriority(Process.THREAD_PRIORITY_AUDIO);
        AudioRecord rec = record;
        if (rec == null) {
            return;
        }
        int chunk = Math.max(sampleRate / 50, 320) * 2;
        byte[] buf = new byte[chunk];
        while (running) {
            int n;
            try {
                n = rec.read(buf, 0, buf.length);
            } catch (Exception e) {
                break;
            }
            if (n <= 0) {
                continue;
            }
            listener.onAudio(buf, n, peak(buf, n));
        }
    }

    private static float peak(byte[] pcm, int length) {
        int max = 0;
        for (int i = 0; i + 1 < length; i += 2) {
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

    static boolean hasMicPermission(Context context) {
        return context.checkSelfPermission(android.Manifest.permission.RECORD_AUDIO)
                == android.content.pm.PackageManager.PERMISSION_GRANTED;
    }
}
