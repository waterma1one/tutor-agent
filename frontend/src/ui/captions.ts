import type { Store } from '../store';
import { byId, element } from './dom';

/** Live captions of the whole conversation, newest at the bottom. */
export function mountCaptions(store: Store): void {
    const list = byId('captions');
    const nodes = new Map<number, HTMLLIElement>();

    store.subscribe((state) => {
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
        list.parentElement!.scrollTop = list.parentElement!.scrollHeight;
    });
}
