import type { State, Store } from '../store';
import { byId } from './dom';

interface Actions {
    togglePause(): void;
    toggleMic(): void;
    leave(): void;
}

/** Pause and mute buttons, the paused veil, the mode badge and Leave. */
export function mountControls(store: Store, actions: Actions): void {
    const pauseButton = byId<HTMLButtonElement>('pause-btn');
    const pauseLabel = pauseButton.querySelector<HTMLElement>('.pause-label')!;
    const veil = byId('paused-veil');
    const badge = byId('mode-badge');
    const leaveButton = byId<HTMLButtonElement>('leave-btn');
    const micButton = byId<HTMLButtonElement>('mic-btn');
    const micLabel = micButton.querySelector<HTMLElement>('.mic-label')!;
    const legend = byId('legend-student');

    pauseButton.addEventListener('click', () => actions.togglePause());
    leaveButton.addEventListener('click', () => actions.leave());
    veil.addEventListener('click', () => actions.togglePause());
    micButton.addEventListener('click', () => actions.toggleMic());

    store.subscribe((state) => {
        // The server ignores pause until the first slide starts.
        pauseButton.disabled = state.slide === null;
        pauseLabel.textContent = state.paused ? 'Resume' : 'Pause';
        pauseButton.setAttribute('aria-pressed', String(state.paused));
        veil.hidden = !state.paused;

        micButton.disabled = state.phase !== 'live';
        micLabel.textContent = state.micMuted ? 'Unmute mic' : 'Mute mic';
        micButton.setAttribute('aria-pressed', String(state.micMuted));
        legend.textContent = state.micMuted ? 'You (mic off)' : 'You';
        legend.classList.toggle('legend-muted', state.micMuted);

        const { text, tone } = badgeFor(state);
        badge.textContent = text;
        badge.dataset.tone = tone;
    });
}

function badgeFor(state: State): { text: string; tone: string } {
    if (state.pendingSlide !== null) return { text: `Going to slide ${state.pendingSlide}`, tone: 'busy' };
    if (state.paused) return { text: 'Paused', tone: 'paused' };
    if (state.studentSpeaking) return { text: 'Listening to you', tone: 'student' };
    if (state.slide === null) return { text: 'Getting ready', tone: 'busy' };
    if (state.mode === 'qna') return { text: 'Questions time', tone: 'tutor' };
    return { text: 'Presenting', tone: 'tutor' };
}
