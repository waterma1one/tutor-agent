import type { State } from './store';

/** The class as plain text, with a heading each time the slide changes. */
export function transcriptText(state: State, when: Date): string {
    const out = [
        'Natural Disasters with Terra',
        `Class transcript, ${when.toLocaleString(undefined, { dateStyle: 'long', timeStyle: 'short' })}`,
    ];
    let slide: number | null | undefined;
    for (const line of state.lines) {
        if (line.slide !== slide) {
            slide = line.slide;
            out.push('', heading(state, slide), '');
        }
        out.push(`${line.speaker === 'tutor' ? 'Terra' : 'You'}: ${line.text}`);
    }
    if (state.lines.length === 0) out.push('', 'Nothing was said in this class.');
    return out.join('\n') + '\n';
}

export function downloadTranscript(state: State): void {
    const when = new Date();
    const blob = new Blob([transcriptText(state, when)], { type: 'text/plain;charset=utf-8' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `terra-class-${when.toISOString().slice(0, 10)}.txt`;
    link.click();
    // Give the browser a moment to start the download before freeing the file.
    window.setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}

function heading(state: State, slide: number | null): string {
    if (slide === null) return 'Before the first slide';
    const title = state.slides.find((s) => s.number === slide)?.title;
    return title ? `Slide ${slide}: ${title}` : `Slide ${slide}`;
}
