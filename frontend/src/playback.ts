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
