import type { State, Store } from '../store';
import { downloadTranscript } from '../transcript';
import { byId, element } from './dom';

/** Shows the screen for the current phase and fills in the end-of-class summary. */
export function mountScreens(store: Store): void {
    const landing = byId('landing');
    const classroom = byId('classroom');
    const ended = byId('ended');
    const startButton = byId<HTMLButtonElement>('start-btn');
    byId('transcript-btn').addEventListener('click', () => downloadTranscript(store.get()));

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

        if (state.phase === 'ended' && previous.phase !== 'ended') renderSummary(state);
    });
}

function renderSummary(state: State): void {
    const total = state.slides.length;
    const covered = state.visited.length;
    const said = state.lines.filter((line) => line.speaker === 'student');

    byId('ended-summary').textContent =
        state.mode === 'qna'
            ? `You heard all ${total} slides and stayed for questions.`
            : covered === 0
              ? 'The class ended before the first slide.'
              : `You got as far as slide ${Math.max(...state.visited)} of ${total}.`;
    byId('stat-slides').textContent = `${covered} of ${total}`;
    byId('stat-spoke').textContent = String(said.length);

    byId('ended-said').hidden = said.length === 0;
    byId('ended-said-list').replaceChildren(
        ...said.map((line) => element('li', undefined, line.text))
    );
    byId<HTMLButtonElement>('transcript-btn').disabled = state.lines.length === 0;
}
