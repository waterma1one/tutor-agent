import { requestsOpen, type State, type Store } from '../store';
import { byId } from './dom';

/**
 * The type-a-question box, for students without a mic or too shy to use it.
 * `ask` resolves with whether the tutor took the question. The box keeps the
 * text, locked, until then, and clears only once it was taken.
 */
export function mountAsk(store: Store, ask: (text: string) => Promise<boolean>): void {
    const form = byId<HTMLFormElement>('ask-form');
    const input = byId<HTMLInputElement>('ask-input');
    const button = byId<HTMLButtonElement>('ask-btn');

    const sync = (state: State) => {
        const open = requestsOpen(state);
        input.disabled = !open;
        button.disabled = !open || !input.value.trim();
        input.placeholder = state.paused ? 'Resume to ask a question' : 'Or type a question…';
    };

    input.addEventListener('input', () => sync(store.get()));
    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const text = input.value.trim();
        if (!text || !requestsOpen(store.get())) return;
        if (await ask(text)) {
            input.value = '';
            sync(store.get());
        }
    });
    store.subscribe((state) => sync(state));
}
