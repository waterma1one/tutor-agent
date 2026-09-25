import type { State, Store } from '../store';
import { byId, element } from './dom';

/** The big slide plate: what the tutor is talking about right now. */
export function mountStage(store: Store): void {
    const plate = byId('slide');
    const count = plate.querySelector<HTMLElement>('.plate-count')!;
    const title = plate.querySelector<HTMLElement>('.plate-title')!;
    const bullets = plate.querySelector<HTMLElement>('.plate-bullets')!;

    let shown = '';
    store.subscribe((state) => {
        const key = `${state.mode}:${state.slide}:${state.slides.length}`;
        if (key === shown) return;
        shown = key;

        const content = plateContent(state);
        count.textContent = content.count;
        title.textContent = content.title;
        bullets.replaceChildren(...content.bullets.map((text) => element('li', undefined, text)));
        plate.dataset.kind = content.kind;
        plate.style.setProperty('--progress', String(content.progress));

        // Restart the entrance animation for the new slide.
        plate.classList.remove('plate-enter');
        void plate.offsetWidth;
        plate.classList.add('plate-enter');
    });
}

function plateContent(state: State) {
    const total = state.slides.length;
    if (state.mode === 'qna') {
        return {
            kind: 'qna',
            count: `All ${total} slides done`,
            title: 'Your questions',
            bullets: [
                'Ask Terra anything about natural disasters.',
                'Pick a slide below to hear it again.',
            ],
            progress: 1,
        };
    }
    const slide = state.slides.find((s) => s.number === state.slide);
    if (!slide) {
        return {
            kind: 'waiting',
            count: `${total} slides`,
            title: 'Terra is getting ready',
            bullets: ['The lesson starts in a moment.'],
            progress: 0,
        };
    }
    return {
        kind: 'slide',
        count: `Slide ${slide.number} of ${total}`,
        title: slide.title,
        bullets: slide.bullets,
        progress: slide.number / total,
    };
}
