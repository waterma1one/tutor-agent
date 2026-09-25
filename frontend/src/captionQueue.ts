import type { SpeechClock } from './playback';

const CHECK_INTERVAL_MS = 50;

/**
 * Holds each caption until the student hears the sentence it belongs to.
 *
 * The server sends a caption just before its sentence's audio, but that audio
 * joins a queue here that can be seconds long. So a caption is stamped with the
 * time the queue ahead of it ends, and shown once the playhead gets there.
 */
export class CaptionQueue {
    private pending: { at: number; text: string }[] = [];
    private clock: SpeechClock | null = null;
    private timer = 0;

    constructor(private readonly show: (text: string) => void) {}

    start(clock: SpeechClock | null): void {
        this.stop();
        this.clock = clock;
        this.timer = window.setInterval(() => this.release(), CHECK_INTERVAL_MS);
    }

    add(text: string): void {
        // Without a clock there is nothing to wait for; show it as it comes.
        if (!this.clock) return this.show(text);
        this.pending.push({ at: this.clock.queuedUntil(), text });
        this.release();
    }

    /** Forgets captions whose speech was dropped, as for a jump. */
    clear(): void {
        this.pending = [];
    }

    stop(): void {
        window.clearInterval(this.timer);
        this.clock?.stop();
        this.clock = null;
        this.pending = [];
    }

    private release(): void {
        const now = this.clock?.now() ?? Infinity;
        while (this.pending.length && this.pending[0].at <= now) {
            this.show(this.pending.shift()!.text);
        }
    }
}
