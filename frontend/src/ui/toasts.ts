import { byId, element } from './dom';

const TOAST_MS = 6000;

/** Shows a short message at the bottom of the screen. */
export function toast(message: string): void {
    const container = byId('toasts');
    const node = element('p', 'toast', message);
    container.append(node);
    window.setTimeout(() => node.remove(), TOAST_MS);
}
