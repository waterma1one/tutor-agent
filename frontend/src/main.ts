import { loadSlides, Session } from './session';
import { Store } from './store';
import { mountCaptions } from './ui/captions';
import { mountAsk } from './ui/ask';
import { mountControls } from './ui/controls';
import { mountLanding } from './ui/landing';
import { mountScreens } from './ui/screens';
import { mountSeismograph } from './ui/seismograph';
import { mountStage } from './ui/stage';
import { mountThumbs } from './ui/thumbs';
import { toast } from './ui/toasts';

const store = new Store();
const session = new Session(store, { onProblem: toast });

mountScreens(store);
mountLanding(() => void session.start());
mountStage(store);
mountCaptions(store);
mountThumbs(store, (n) => void session.goToSlide(n));
mountControls(store, {
    togglePause: () => void session.togglePause(),
    leave: () => void session.leave(),
});
mountAsk(store, (text) => session.ask(text));
mountSeismograph(store, () => session.levels());

loadSlides()
    .then((slides) => store.set({ slides }))
    .catch((error) => {
        console.error(error);
        toast('Could not load the lesson. Start the tutor server, then reload this page.');
    });

// Lets browser tests put the UI into any state without a live session.
if (import.meta.env.DEV) Object.assign(window, { tutorStore: store });
