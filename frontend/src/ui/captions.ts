import type { Store } from '../store';
import { byId, element } from './dom';

// How close to the bottom counts as following along, in pixels.
const FOLLOW_SLACK_PX = 40;

/**
 * Live captions of the whole conversation, newest at the bottom. Follows new
 * lines unless the student has scrolled back to reread.
 */
export function mountCaptions(store: Store): void {
    const list = byId('captions');
    const scroller = list.parentElement!;
    const nodes = new Map<number, HTMLLIElement>();
    // Scrolling is smooth, so mid-way through following a line the view is not
    // at the bottom yet. Until it settles, keep following.
    let autoScrolling = false;
    scroller.addEventListener('scrollend', () => (autoScrolling = false));

    store.subscribe((state, previous) => {
        if (state.lines === previous.lines) return;
        const following =
            autoScrolling ||
            scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight <= FOLLOW_SLACK_PX;
        if (state.lines.length === 0 && nodes.size > 0) {
            list.replaceChildren();
            nodes.clear();
        }
        for (const line of state.lines) {
            let node = nodes.get(line.id);
            if (!node) {
                node = element('li', `caption caption-${line.speaker}`);
                node.append(
                    element('span', 'caption-speaker', line.speaker === 'tutor' ? 'Terra' : 'You'),
                    element('span', 'caption-text')
                );
                nodes.set(line.id, node);
                list.append(node);
            }
            const text = node.querySelector('.caption-text')!;
            if (text.textContent !== line.text) text.textContent = line.text;
        }
        const latest = state.lines.at(-1);
        list.querySelectorAll('.caption-latest').forEach((n) => n.classList.remove('caption-latest'));
        if (latest) nodes.get(latest.id)?.classList.add('caption-latest');
        if (following && scroller.scrollHeight > scroller.clientHeight) {
            autoScrolling = true;
            scroller.scrollTop = scroller.scrollHeight;
        }
    });
}
