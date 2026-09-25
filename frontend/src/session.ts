/**
 * One class session: the Pipecat client, the lesson requests the student makes,
 * and the store updates that follow from what the tutor sends back.
 */
import { PipecatClient } from '@pipecat-ai/client-js';
import { WebSocketTransport } from '@pipecat-ai/websocket-transport';
import {
    interruptPlayback,
    releaseInterruption,
    resumePlayback,
    suspendPlayback,
    trackQueuedSpeech,
    tutorLevel,
    watchPlayback,
} from './playback';
import { CaptionQueue } from './captionQueue';
import { MicLevel } from './micLevel';
import type { Line, Mode, Slide, Store } from './store';
import { initialState } from './store';

interface LessonState {
    type: 'lesson-state';
    mode: Mode;
    slide: number | null;
    total: number;
    paused: boolean;
    /** The id of the client request this state answers, if any. */
    request: string | null;
}

export interface SessionEvents {
    /** Something went wrong that the student should hear about. */
    onProblem(message: string): void;
}

export async function loadSlides(): Promise<Slide[]> {
    const response = await fetch('/slides');
    if (!response.ok) throw new Error(`GET /slides answered ${response.status}`);
    return response.json();
}

export class Session {
    private client: PipecatClient | null = null;
    private stopWatchingPlayback: (() => void) | null = null;
    private nextRequest = 1;
    /** The pause/resume request still waiting for its reply. */
    private pendingPause: string | null = null;
    /** The jump request still waiting for its reply, and its slide. */
    private pendingJump: { id: string; slide: number } | null = null;
    private pendingQuestion: string | null = null;
    private nextLine = 1;
    /** The tutor line captions are appending to; a new one starts per reply. */
    private tutorLine: Line | null = null;
    private leaving = false;
    private mic = new MicLevel();
    private captions = new CaptionQueue((text) => this.appendTutorText(text));

    constructor(
        private store: Store,
        private events: SessionEvents
    ) {}

    async start(): Promise<void> {
        const store = this.store;
        store.set({ ...initialState, slides: store.get().slides, phase: 'connecting' });
        this.leaving = false;

        const client = new PipecatClient({
            transport: new WebSocketTransport(),
            enableMic: true,
            enableCam: false,
            callbacks: {
                onBotReady: () => {
                    this.mic.attach(client.tracks().local.audio);
                    const clock = trackQueuedSpeech(client);
                    if (!clock) console.warn('No audio player yet; captions will not wait for speech.');
                    this.captions.start(clock);
                    this.stopWatchingPlayback = watchPlayback(client, (playing) =>
                        this.send(playing ? 'playback-started' : 'playback-idle')
                    );
                },
                onDisconnected: () => this.finish(),
                onServerMessage: (data) => {
                    if (data?.type === 'lesson-state') this.applyLessonState(data);
                    // Sent just ahead of each sentence's audio and held until it plays;
                    // the standard bot-tts-text only arrives once the sentence has ended.
                    else if (data?.type === 'caption') this.captions.add(data.text);
                },
                onBotStartedSpeaking: () => {
                    // New speech has started, so the old speech a jump cut off
                    // has stopped arriving.
                    releaseInterruption(client);
                    store.set({ tutorSpeaking: true });
                },
                onBotStoppedSpeaking: () => store.set({ tutorSpeaking: false }),
                onUserStartedSpeaking: () => {
                    this.tutorLine = null;
                    store.set({ studentSpeaking: true });
                },
                onUserStoppedSpeaking: () => store.set({ studentSpeaking: false }),
                onBotLlmStarted: () => {
                    this.tutorLine = null;
                },
                onUserTranscript: (data) => {
                    if (data.final && data.text.trim()) this.addStudentLine(data.text.trim());
                },
                onError: (message) => console.error('Pipecat error', message),
            },
        });
        this.client = client;

        try {
            await client.initDevices();
            store.set({ connectStep: 'tutor' });
            await client.startBotAndConnect({ endpoint: '/connect' });
            store.set({ phase: 'live' });
        } catch (error) {
            console.error(error);
            this.events.onProblem(describeConnectError(error));
            await this.leave();
            store.set({ phase: 'landing' });
        }
    }

    async leave(): Promise<void> {
        this.leaving = true;
        const client = this.client;
        if (!client) return;
        try {
            await client.disconnect();
        } catch (error) {
            console.warn('Disconnect failed', error);
        }
        this.finish();
    }

    /**
     * Pauses or resumes the lesson.
     *
     * On pause the browser stops its own audio before asking the server to hold
     * the rest; on resume it restarts its queue first so the server's held
     * audio lands behind what was already buffered here.
     */
    async togglePause(): Promise<void> {
        const client = this.client;
        if (!client || this.store.get().slide === null) return;
        const pausing = !this.store.get().paused;
        this.store.set({ paused: pausing });
        if (pausing) {
            if (!(await suspendPlayback(client))) {
                this.events.onProblem('Speech already playing could not be paused.');
            }
            client.enableMic(false);
        } else {
            await resumePlayback(client);
            client.enableMic(true);
        }
        this.pendingPause = this.send(pausing ? 'pause' : 'resume');
    }

    async goToSlide(slide: number): Promise<void> {
        const client = this.client;
        const state = this.store.get();
        if (!client || state.paused || state.slide === null || this.pendingJump) return;
        this.tutorLine = null;
        this.store.set({ pendingSlide: slide });
        await interruptPlayback(client);
        this.captions.clear();
        const id = this.send('go-to-slide', { slide });
        this.pendingJump = id ? { id, slide } : null;
        if (!id) this.store.set({ pendingSlide: null });
    }

    /** Puts a typed question to the tutor, cutting off what it is saying. */
    ask(text: string): boolean {
        const client = this.client;
        const state = this.store.get();
        if (!client || state.paused || state.slide === null || this.pendingJump) return false;
        const id = this.send('ask', { text });
        if (!id) return false;
        this.pendingQuestion = id;
        this.addStudentLine(text);
        this.captions.clear();
        void interruptPlayback(client);
        return true;
    }

    /** Current voice levels, 0 to 1, for the voice meter. The mic reads 0 while paused. */
    levels(): { tutor: number; student: number } {
        const client = this.client;
        if (!client) return { tutor: 0, student: 0 };
        const paused = this.store.get().paused;
        return { tutor: tutorLevel(client), student: paused ? 0 : this.mic.level() };
    }

    /** Sends a client message tagged with a fresh request id, or null if offline. */
    private send(type: string, data: Record<string, unknown> = {}): string | null {
        const client = this.client;
        if (!client) return null;
        const request = `r${this.nextRequest++}`;
        try {
            client.sendClientMessage(type, { ...data, request });
            return request;
        } catch (error) {
            console.warn(`Could not send ${type}`, error);
            return null;
        }
    }

    private applyLessonState(state: LessonState): void {
        const patch: Partial<typeof initialState> = { slide: state.slide, mode: state.mode };
        const { visited } = this.store.get();
        if (state.slide !== null && !visited.includes(state.slide)) {
            patch.visited = [...visited, state.slide];
        }

        // While a pause or resume is in flight, older replies describe a state
        // the student has already left. The reply to the latest request wins,
        // even when the server refused it (for example, before the lesson began).
        if (this.pendingPause === null || state.request === this.pendingPause) {
            this.pendingPause = null;
            if (state.paused !== this.store.get().paused) this.syncLocalPause(state.paused);
            patch.paused = state.paused;
        }

        if (this.pendingQuestion && state.request === this.pendingQuestion) {
            // The server only turns a question down while paused.
            if (state.paused && this.client) {
                releaseInterruption(this.client);
                this.events.onProblem('Your question was not sent because the class is paused.');
            }
            this.pendingQuestion = null;
        }

        if (this.pendingJump && state.request === this.pendingJump.id) {
            if (state.slide !== this.pendingJump.slide && this.client) {
                // Refused: nothing new is coming, so stop dropping speech.
                releaseInterruption(this.client);
                this.events.onProblem(`Could not go to slide ${this.pendingJump.slide}.`);
            }
            this.pendingJump = null;
            patch.pendingSlide = null;
        }
        this.store.set(patch);
    }

    /** Brings the browser's audio and mic in line with the server's pause state. */
    private syncLocalPause(paused: boolean): void {
        const client = this.client;
        if (!client) return;
        if (paused) {
            void suspendPlayback(client);
        } else {
            void resumePlayback(client);
        }
        client.enableMic(!paused);
    }

    private appendTutorText(text: string): void {
        const lines = this.store.get().lines;
        if (this.tutorLine && lines.at(-1)?.id === this.tutorLine.id) {
            const joined = joinWords(this.tutorLine.text, text);
            this.tutorLine = { ...this.tutorLine, text: joined };
            this.store.set({ lines: [...lines.slice(0, -1), this.tutorLine] });
        } else {
            this.tutorLine = {
                id: this.nextLine++,
                speaker: 'tutor',
                text: text.trim(),
                slide: this.store.get().slide,
            };
            this.store.set({ lines: [...lines, this.tutorLine] });
        }
    }

    private addStudentLine(text: string): void {
        this.tutorLine = null;
        const line: Line = {
            id: this.nextLine++,
            speaker: 'student',
            text,
            slide: this.store.get().slide,
        };
        this.store.set({ lines: [...this.store.get().lines, line] });
    }

    private finish(): void {
        if (!this.client) return;
        this.stopWatchingPlayback?.();
        this.stopWatchingPlayback = null;
        this.captions.stop();
        this.mic.detach();
        this.client = null;
        this.pendingPause = null;
        this.pendingJump = null;
        this.pendingQuestion = null;
        const wasLive = this.store.get().phase === 'live';
        this.store.set({
            phase: wasLive ? 'ended' : this.store.get().phase,
            tutorSpeaking: false,
            studentSpeaking: false,
            paused: false,
            pendingSlide: null,
        });
        if (wasLive && !this.leaving) {
            this.events.onProblem('The connection to the tutor dropped.');
        }
    }
}

/** TTS text arrives in word-sized pieces, some with their own leading space. */
function joinWords(text: string, piece: string): string {
    if (!text) return piece.trim();
    if (/^\s/.test(piece) || /^[,.!?;:]/.test(piece)) return text + piece;
    return `${text} ${piece}`;
}

function describeConnectError(error: unknown): string {
    const name = (error as { name?: string })?.name;
    if (name === 'NotAllowedError') {
        return 'Microphone access is blocked. Allow it in the address bar, then start again.';
    }
    if (name === 'NotFoundError') return 'No microphone found. Plug one in, then start again.';
    return 'Could not reach the tutor. Check that the server is running, then start again.';
}
