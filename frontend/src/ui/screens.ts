import type { Store } from '../store';
import { byId } from './dom';

/** Shows the screen for the current phase and fills in the end-of-class summary. */
export function mountScreens(store: Store): void {
    const landing = byId('landing');
    const classroom = byId('classroom');
    const ended = byId('ended');
    const startButton = byId<HTMLButtonElement>('start-btn');
    const summary = byId('ended-summary');

    store.subscribe((state, previous) => {
        landing.hidden = !(state.phase === 'landing' || state.phase === 'connecting');
        classroom.hidden = state.phase !== 'live';
        ended.hidden = state.phase !== 'ended';

        const connecting = state.phase === 'connecting';
        startButton.disabled = connecting || state.slides.length === 0;
        startButton.textContent = !connecting
            ? 'Start class'
            : state.connectStep === 'mic'
              ? 'Allow the microphone…'
              : 'Calling Terra…';
        startButton.setAttribute('aria-busy', String(connecting));

        if (state.phase === 'ended' && previous.phase !== 'ended') {
            const reached = state.slide ?? 0;
            const questions = state.lines.filter((line) => line.speaker === 'student').length;
            const progress =
                state.mode === 'qna'
                    ? `You heard all ${state.slides.length} slides and stayed for questions.`
                    : `You got to slide ${reached} of ${state.slides.length}.`;
            const spoke =
                questions === 0 ? 'You did not ask anything this time.'
                : questions === 1 ? 'You spoke once.'
                : `You spoke ${questions} times.`;
            summary.textContent = `${progress} ${spoke}`;
        }
    });
}
