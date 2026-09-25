import type { State, Store } from '../store';
import { byId } from './dom';

/**
 * The type-a-question box, for students without a mic or too shy to use it.
 * `ask` returns whether the question was sent; the text stays put if not.
 */
export function mountAsk(store: Store, ask: (text: string) => boolean): void {
    const form = byId<HTMLFormElement>('ask-form');
    const input = byId<HTMLInputElement>('ask-input');
    const button = byId<HTMLButtonElement>('ask-btn');

    const sync = (state: State) => {
        const open = canAsk(state);
        input.disabled = !open;
        button.disabled = !open || !input.value.trim();
        input.placeholder = state.paused ? 'Resume to ask a question' : 'Or type a question…';
    };

    input.addEventListener('input', () => sync(store.get()));
    form.addEventListener('submit', (event) => {
        event.preventDefault();
        const text = input.value.trim();
        if (!text || !canAsk(store.get())) return;
        if (ask(text)) {
            input.value = '';
            sync(store.get());
        }
    });
    store.subscribe((state) => sync(state));
}

function canAsk(state: State): boolean {
    return (
        state.phase === 'live' &&
        !state.paused &&
        state.slide !== null &&
        state.pendingSlide === null
    );
}
