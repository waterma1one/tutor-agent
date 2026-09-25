import type { Store } from '../store';
import { byId } from './dom';

interface Actions {
    togglePause(): void;
    toggleMic(): void;
    goToSlide(n: number): void;
}

/**
 * Keyboard shortcuts for the classroom, and the `?` list that explains them.
 * Keys only act while class is live and never while the student is typing.
 */
export function mountShortcuts(store: Store, actions: Actions): void {
    const dialog = byId<HTMLDialogElement>('keys-dialog');
    const askInput = byId<HTMLInputElement>('ask-input');
    byId('keys-btn').addEventListener('click', () => dialog.showModal());

    askInput.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') askInput.blur();
    });

    document.addEventListener('keydown', (event) => {
        const state = store.get();
        if (state.phase !== 'live' || dialog.open) return;
        if (event.repeat || event.ctrlKey || event.metaKey || event.altKey) return;
        if (isTyping(event.target)) return;
        // Space on a focused button presses that button.
        if (event.code === 'Space' && event.target instanceof HTMLButtonElement) return;

        const slide = Number(event.key);
        if (event.code === 'Space') {
            if (state.slide === null) return;
            actions.togglePause();
        } else if (event.key === 'm' || event.key === 'M') {
            actions.toggleMic();
        } else if (event.key === '/') {
            if (askInput.disabled) return;
            askInput.focus();
        } else if (event.key === '?') {
            dialog.showModal();
        } else if (Number.isInteger(slide) && slide >= 1 && slide <= state.slides.length) {
            actions.goToSlide(slide);
        } else {
            return;
        }
        event.preventDefault();
    });
}

/** Keys typed into a field keep their usual meaning. */
function isTyping(target: EventTarget | null): boolean {
    return (
        target instanceof HTMLElement &&
        (target.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName))
    );
}
