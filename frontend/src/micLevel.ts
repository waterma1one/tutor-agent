import { rms } from './playback';

/** Measures the student's microphone from its public media track. */
export class MicLevel {
    private context: AudioContext | null = null;
    private analyser: AnalyserNode | null = null;
    private trackId: string | null = null;

    /** Starts measuring `track`, or keeps going if it is the same one. */
    attach(track: MediaStreamTrack | undefined): void {
        if (!track || track.id === this.trackId) return;
        this.detach();
        this.trackId = track.id;
        this.context = new AudioContext();
        this.analyser = this.context.createAnalyser();
        this.analyser.fftSize = 1024;
        this.context.createMediaStreamSource(new MediaStream([track])).connect(this.analyser);
    }

    detach(): void {
        void this.context?.close();
        this.context = null;
        this.analyser = null;
        this.trackId = null;
    }

    level(): number {
        return this.analyser ? rms(this.analyser) : 0;
    }
}
