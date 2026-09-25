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

function playerContext(client: PipecatClient): AudioContext | null {
    // WebSocketTransport -> WavMediaManager -> WavStreamPlayer
    const transport = client.transport as any;
    const context = transport?._mediaManager?._wavStreamPlayer?.context;
    return context instanceof AudioContext ? context : null;
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
