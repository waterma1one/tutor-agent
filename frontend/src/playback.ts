/**
 * Freezes and resumes the tutor's audio in the browser.
 *
 * The server sends speech at twice real time, so up to half an utterance can be
 * queued here when the student presses pause. Suspending the player's
 * AudioContext stops on the exact sample and keeps the queue; chunks that are
 * still arriving join the queue behind it. See docs/NOTES.md.
 *
 * The websocket transport has no public API for this, so this module is the
 * one place that reaches into its private fields.
 */
import type { PipecatClient } from '@pipecat-ai/client-js';

function player(client: PipecatClient): any {
    // WebSocketTransport -> WavMediaManager -> WavStreamPlayer
    const transport = client.transport as any;
    return transport?._mediaManager?._wavStreamPlayer ?? null;
}

function playerContext(client: PipecatClient): AudioContext | null {
    const context = player(client)?.context;
    return context instanceof AudioContext ? context : null;
}

const WATCH_INTERVAL_MS = 100;

/**
 * Reports when the tutor's queued speech starts and stops playing here.
 *
 * The server finishes sending speech long before the student hears the end of
 * it, so it asks the browser. The player keeps a worklet node (`stream`) while
 * it has audio queued, including while suspended by a pause, and drops it once
 * the queue runs dry or is interrupted. Returns a function that stops watching.
 */
export function watchPlayback(
    client: PipecatClient,
    onChange: (playing: boolean) => void
): () => void {
    let playing = false;
    const timer = window.setInterval(() => {
        const now = player(client)?.stream != null;
        if (now !== playing) {
            playing = now;
            onChange(now);
        }
    }, WATCH_INTERVAL_MS);
    return () => window.clearInterval(timer);
}

export async function suspendPlayback(client: PipecatClient): Promise<boolean> {
    const context = playerContext(client);
    if (!context) return false;
    await context.suspend();
    return true;
}

export async function resumePlayback(client: PipecatClient): Promise<boolean> {
    const context = playerContext(client);
    if (!context) return false;
    await context.resume();
    return true;
}

/**
 * Drops the tutor's queued speech here, for a jump the student asked for.
 *
 * The transport never interrupts its own player, and the player's `interrupt`
 * blocks the track id every chunk shares ("default"), so all later speech
 * would be dropped too. That block is useful for a moment: it discards the
 * old speech still in flight from the server. Call `releaseInterruption` once
 * that speech has stopped arriving.
 */
export async function interruptPlayback(client: PipecatClient): Promise<void> {
    await player(client)?.interrupt();
}

export function releaseInterruption(client: PipecatClient): void {
    const p = player(client);
    if (p?.interruptedTrackIds) p.interruptedTrackIds = {};
}

let levelBuffer: Float32Array<ArrayBuffer> | null = null;

/** How loud the tutor's speech playing here is right now, from 0 to 1. */
export function tutorLevel(client: PipecatClient): number {
    const analyser = player(client)?.analyser;
    if (!(analyser instanceof AnalyserNode) || player(client)?.stream == null) return 0;
    return loudness(analyser);
}

// Speech sits roughly between -45 and -15 dBFS, so a linear RMS barely moves the trace.
// Map loudness onto 0..1 on a decibel scale instead; this range keeps ordinary speech
// under half height and quiet background noise at zero.
const QUIET_DB = -50;
const LOUD_DB = -5;

/** Loudness of the analyser's current window, from 0 (quiet) to 1 (loud). */
export function loudness(analyser: AnalyserNode): number {
    if (!levelBuffer || levelBuffer.length !== analyser.fftSize) {
        levelBuffer = new Float32Array(analyser.fftSize);
    }
    analyser.getFloatTimeDomainData(levelBuffer);
    let sum = 0;
    for (const sample of levelBuffer) sum += sample * sample;
    const db = 10 * Math.log10(sum / levelBuffer.length + 1e-12);
    return Math.min(1, Math.max(0, (db - QUIET_DB) / (LOUD_DB - QUIET_DB)));
}

export interface SpeechClock {
    /** The player's clock now, in seconds; it stands still while paused. */
    now(): number;
    /** When the speech queued so far finishes playing, on the same clock. */
    queuedUntil(): number;
    stop(): void;
}

/**
 * Follows how far ahead of the student's ears the received speech runs.
 *
 * Sent at twice real time, speech piles up here, so anything the server sends
 * alongside it (captions) arrives early. Every chunk the player accepts extends
 * the queue from its end, or from now if the queue has run dry; the player's
 * AudioContext time is the playhead, and suspending it for a pause stops it.
 * An interruption empties the queue, so the next speech starts from now.
 */
export function trackQueuedSpeech(client: PipecatClient): SpeechClock | null {
    const p = player(client);
    const context = playerContext(client);
    if (!p || !context) return null;

    let endsAt = 0;
    const add = p.add16BitPCM;
    const interrupt = p.interrupt;
    p.add16BitPCM = function (data: unknown, trackId?: string) {
        const buffer: Int16Array | undefined = add.call(this, data, trackId);
        if (buffer) {
            const rate: number = p.sampleRate ?? context.sampleRate;
            endsAt = Math.max(endsAt, context.currentTime) + buffer.length / rate;
        }
        return buffer;
    };
    p.interrupt = function (...args: unknown[]) {
        endsAt = context.currentTime;
        return interrupt.apply(this, args);
    };
    return {
        now: () => context.currentTime,
        queuedUntil: () => Math.max(endsAt, context.currentTime),
        stop: () => {
            p.add16BitPCM = add;
            p.interrupt = interrupt;
        },
    };
}
