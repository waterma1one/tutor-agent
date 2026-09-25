/**
 * The whole UI state in one place.
 *
 * Views subscribe and re-render from the state they are given; only the
 * session writes to it. Audio levels change 60 times a second and bypass the
 * store (see `seismograph.ts`).
 */

export type Mode = 'presenting' | 'qna';

/** Where the student is in the app, from the landing page to the end of class. */
export type Phase = 'landing' | 'connecting' | 'live' | 'ended';

export interface Slide {
    number: number;
    title: string;
    bullets: string[];
}

export interface Line {
    id: number;
    speaker: 'tutor' | 'student';
    text: string;
    /** The slide on screen when it was said; null before the first slide. */
    slide: number | null;
}

export interface State {
    phase: Phase;
    slides: Slide[];
    /** The slide the tutor is on; null until the lesson starts. */
    slide: number | null;
    mode: Mode;
    paused: boolean;
    /** The student switched their mic off; it stays off through pause and resume. */
    micMuted: boolean;
    tutorSpeaking: boolean;
    studentSpeaking: boolean;
    /** Everything said so far, oldest first. */
    lines: Line[];
    /** Slides presented so far, in the order they were first shown. */
    visited: number[];
    /** A slide the student asked for that the tutor has not moved to yet. */
    pendingSlide: number | null;
    /** A typed question is waiting for the tutor to take it. */
    pendingQuestion: boolean;
    /** While connecting: waiting for mic permission, then for the tutor. */
    connectStep: 'mic' | 'tutor';
}

export const initialState: State = {
    phase: 'landing',
    slides: [],
    slide: null,
    mode: 'presenting',
    paused: false,
    micMuted: false,
    tutorSpeaking: false,
    studentSpeaking: false,
    lines: [],
    visited: [],
    pendingSlide: null,
    pendingQuestion: false,
    connectStep: 'mic',
};

type Listener = (state: State, previous: State) => void;

export class Store {
    private state: State = initialState;
    private listeners = new Set<Listener>();

    get(): State {
        return this.state;
    }

    set(patch: Partial<State>): void {
        const previous = this.state;
        this.state = { ...previous, ...patch };
        this.listeners.forEach((listener) => listener(this.state, previous));
    }

    /** Calls `listener` now and after every change. Returns an unsubscribe function. */
    subscribe(listener: Listener): () => void {
        this.listeners.add(listener);
        listener(this.state, this.state);
        return () => this.listeners.delete(listener);
    }
}
