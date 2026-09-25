import { byId } from './dom';

/** Wires the Start button and draws the landing page's seismogram. */
export function mountLanding(start: () => void): void {
    byId('start-btn').addEventListener('click', start);
    byId('again-btn').addEventListener('click', start);
    const path = byId('landing-trace-path');
    path.setAttribute('d', quakePath(600, 160));
    // Lets CSS draw the line in without knowing its real length.
    path.setAttribute('pathLength', '1');
}

/**
 * A still trace that shakes into a quake and settles again. Seeded so the page
 * looks the same on every visit.
 */
function quakePath(width: number, height: number): string {
    let seed = 7;
    const random = () => {
        seed = (seed * 16807) % 2147483647;
        return seed / 2147483647;
    };
    const middle = height / 2;
    const points: string[] = [];
    for (let x = 0, i = 0; x <= width; x += 4, i++) {
        const distance = Math.abs(x - width * 0.62) / (width * 0.18);
        const energy = Math.exp(-distance * distance) * 0.92 + 0.03;
        const swing = (i % 2 === 0 ? 1 : -1) * (0.35 + random() * 0.65);
        points.push(`${x},${(middle - swing * energy * middle).toFixed(1)}`);
    }
    return `M${points.join(' L')}`;
}
