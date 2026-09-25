import type { State, Store } from '../store';
import { byId } from './dom';

interface Actions {
    togglePause(): void;
    leave(): void;
}

/** Pause button, Space shortcut, the paused veil, the mode badge and Leave. */
export function mountControls(store: Store, actions: Actions): void {
    const pauseButton = byId<HTMLButtonElement>('pause-btn');
    const pauseLabel = pauseButton.querySelector<HTMLElement>('.pause-label')!;
    const veil = byId('paused-veil');
    const badge = byId('mode-badge');
    const leaveButton = byId<HTMLButtonElement>('leave-btn');

    pauseButton.addEventListener('click', () => actions.togglePause());
    leaveButton.addEventListener('click', () => actions.leave());
    veil.addEventListener('click', () => actions.togglePause());

    document.addEventListener('keydown', (event) => {
        if (event.code !== 'Space' || event.repeat || isTyping(event.target)) return;
        if (store.get().phase !== 'live' || pauseButton.disabled) return;
        event.preventDefault();
        actions.togglePause();
    });

    store.subscribe((state) => {
        // The server ignores pause until the first slide starts.
        pauseButton.disabled = state.slide === null;
        pauseLabel.textContent = state.paused ? 'Resume' : 'Pause';
        pauseButton.setAttribute('aria-pressed', String(state.paused));
        veil.hidden = !state.paused;

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

/** Space in a text field or on a focused control keeps its usual meaning. */
function isTyping(target: EventTarget | null): boolean {
    return (
        target instanceof HTMLElement &&
        (target.isContentEditable || /^(INPUT|TEXTAREA|SELECT|BUTTON)$/.test(target.tagName))
    );
}
