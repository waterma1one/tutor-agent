import type { Store } from '../store';
import { byId, element } from './dom';

/** The row of slides. Picking one asks Terra to go there. */
export function mountThumbs(store: Store, goToSlide: (n: number) => void): void {
    const nav = byId('thumbs');
    let built = 0;

    store.subscribe((state) => {
        if (built !== state.slides.length) {
            built = state.slides.length;
            nav.replaceChildren(
                ...state.slides.map((slide) => {
                    const button = element('button', 'thumb');
                    button.type = 'button';
                    button.dataset.slide = String(slide.number);
                    button.append(
                        element('span', 'thumb-number', String(slide.number)),
                        element('span', 'thumb-title', slide.title)
                    );
                    button.addEventListener('click', () => goToSlide(slide.number));
                    return button;
                })
            );
        }

        const locked = state.paused || state.slide === null || state.pendingSlide !== null;
        nav.querySelectorAll<HTMLButtonElement>('.thumb').forEach((button) => {
            const number = Number(button.dataset.slide);
            const current = state.mode === 'presenting' && number === state.slide;
            button.disabled = locked;
            const done = state.mode === 'qna' || (state.slide !== null && number < state.slide);
            button.classList.toggle('thumb-done', done);
            button.classList.toggle('thumb-pending', number === state.pendingSlide);
            if (current) button.setAttribute('aria-current', 'step');
            else button.removeAttribute('aria-current');
            button.title = current ? 'Terra is on this slide' : `Go to slide ${number}`;
        });
    });
}
