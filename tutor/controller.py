"""Connects the pipecat pipeline to the presentation state machine.

The controller watches speaking frames to decide when the tutor is idle, feeds
those events to `Presentation`, and turns the actions it returns into stage
directions for the LLM plus state updates for the UI.
"""

import asyncio
from collections import deque
from collections.abc import Awaitable, Callable, Sequence
from functools import partial
from typing import Protocol

from loguru import logger
from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    CancelFrame,
    EndFrame,
    Frame,
    FunctionCallResultProperties,
    InterruptionFrame,
    InterruptionWorkerFrame,
    LLMMessagesAppendFrame,
    LLMMessagesTransformFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.observers.base_observer import BaseObserver, FramePushed
from pipecat.services.llm_service import FunctionCallParams

from tutor import prompts
from tutor.presentation import Action, ContinueSlide, Present, Presentation, StartQna
from tutor.slides import Slide

QueueFrames = Callable[[list[Frame]], Awaitable[None]]
Notify = Callable[[dict], Awaitable[None]]


class SpeechGate(Protocol):
    async def pause(self) -> None: ...

    async def resume(self) -> None: ...


_WATCHED = (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
    InterruptionFrame,
    EndFrame,
    CancelFrame,
)


class LessonController(BaseObserver):
    # Long enough for any real question, short enough to keep a paste out of context.
    MAX_QUESTION_CHARS = 500

    def __init__(
        self,
        deck: Sequence[Slide],
        *,
        queue_frames: QueueFrames,
        notify: Notify,
        speech_gate: SpeechGate,
        idle_secs: float = 2.0,
        no_reply_secs: float = 6.0,
        reply_timeout_secs: float = 15.0,
    ):
        super().__init__()
        self.deck = deck
        self.presentation = Presentation(slide_count=len(deck))
        self._queue_frames = queue_frames
        self._notify = notify
        self._speech_gate = speech_gate
        self._bot_speaking = False
        self._user_speaking = False
        # The server finishes sending speech well before the student hears the
        # end of it. Clients that report their playback let the countdown start
        # when the audio actually runs out; others fall back to server timing.
        self._client_playing = False
        # Set once the session ends; nothing may reach the LLM or UI after it.
        self._ended = False
        self._idle_secs = idle_secs
        self._no_reply_secs = no_reply_secs
        self._idle_task: asyncio.Task | None = None
        self._idle_delay: float | None = None
        # The countdown that was running when the lesson was paused.
        self._paused_delay: float | None = None
        # What the student asked for in the UI (a slide jump or a typed
        # question), carried out once the tutor's current speech is cut off.
        self._after_interruption: Callable[[], Awaitable[None]] | None = None
        # Set after that until the tutor starts replying, so the end of the
        # speech that was cut off does not start a countdown.
        self._awaiting_new_speech = False
        # Stops that wait if the reply never makes a sound (an LLM or TTS
        # error), which would otherwise freeze the lesson. Long, so a slow
        # reply is not answered twice.
        self._reply_timeout_secs = reply_timeout_secs
        self._reply_timeout_task: asyncio.Task | None = None
        # Observers see a frame once per processor hop, and the output transport
        # pushes paired copies up and downstream. Remember recent ids so each
        # speaking event is handled once.
        self._seen_ids: deque[int] = deque(maxlen=64)

    def snapshot(self, request: str | None = None, *, refused: bool = False) -> dict:
        """The lesson state for the UI.

        `request` names the client request it answers, and `refused` says the
        request was turned down, which the state alone cannot always show.
        """
        return {
            "type": "lesson-state",
            "mode": self.presentation.mode.value,
            "slide": self.presentation.slide,
            "total": len(self.deck),
            "paused": self.presentation.paused,
            "request": request,
            "refused": refused,
        }

    async def start(self) -> None:
        await self._perform(self.presentation.start())

    async def stop(self) -> None:
        """End the lesson for good: stop timers and ignore everything after."""
        self._ended = True
        self._cancel_idle()
        self._cancel_reply_timeout()

    async def pause(self, request: str | None = None) -> None:
        if self._ended:
            return
        if self.presentation.pause():
            self._paused_delay = self._idle_delay
            self._cancel_idle()
            await self._speech_gate.pause()
        # Always report back, so a client that asked too early is corrected.
        await self._notify(self.snapshot(request))

    async def resume(self, request: str | None = None) -> None:
        if self._ended:
            return
        if self.presentation.resume():
            await self._speech_gate.resume()
            # Held speech restarts the normal speaking/idle cycle. If the tutor
            # was silent and the student is not mid-question, restart the
            # countdown that pausing interrupted; the longer no-reply wait must
            # not shrink to the idle delay.
            if self._ready_to_count_down():
                self._schedule_idle(self._paused_delay or self._idle_secs)
            self._paused_delay = None
        await self._notify(self.snapshot(request))

    async def request_slide(self, number: int, request: str | None = None) -> None:
        """The student picked a slide in the UI: cut the tutor off and present it.

        The slide is presented only once the interruption has passed through the
        pipeline, so the interruption cannot cancel the new slide's response.
        The reply comes then; a refused jump is answered straight away. Only one
        such request runs at a time; another arriving before it is carried out
        is refused.
        """
        if self._ended:
            return
        if self._requests_blocked() or not 1 <= number <= len(self.deck):
            logger.info(f"Refused jump to slide {number}")
            await self._notify(self.snapshot(request, refused=True))
            return
        await self._interrupt_then(partial(self._jump, number, request))

    async def ask(self, text: object, request: str | None = None) -> None:
        """The student typed a question: cut the tutor off and put it to them.

        It is handled like a spoken question, so once answered the tutor bridges
        back to the slide. Blank questions, questions while paused and questions
        while another request is pending are refused.
        """
        if self._ended:
            return
        question = text.strip()[: self.MAX_QUESTION_CHARS] if isinstance(text, str) else ""
        if self._requests_blocked() or not question:
            logger.info("Refused typed question")
            await self._notify(self.snapshot(request, refused=True))
            return
        self.presentation.on_user_spoke()
        await self._interrupt_then(partial(self._put_question, question, request))

    async def on_playback(self, playing: bool) -> None:
        """Client report: its speaker queue started playing or ran dry."""
        if self._ended:
            return
        logger.debug(f"Client playback {'started' if playing else 'idle'}")
        self._client_playing = playing
        if playing:
            self._cancel_idle()
        elif self._ready_to_count_down():
            self._schedule_idle(self._idle_secs)

    async def handle_go_to_slide(self, params: FunctionCallParams) -> None:
        """LLM tool handler for `go_to_slide`."""
        number = params.arguments.get("slide_number")
        try:
            action = self.presentation.go_to(int(number))
        except (TypeError, ValueError) as e:
            await params.result_callback({"ok": False, "error": str(e)})
            return

        logger.info(f"Student asked for slide {number}")
        # Add the new stage direction only after the tool result is in context;
        # OpenAI requires tool results to directly follow the tool call.
        await params.result_callback(
            {"ok": True, "slide": number},
            properties=FunctionCallResultProperties(
                run_llm=False,
                on_context_updated=partial(self._perform, action),
            ),
        )

    async def on_push_frame(self, data: FramePushed) -> None:
        frame = data.frame
        if self._ended or not isinstance(frame, _WATCHED) or self._already_seen(frame):
            return
        if isinstance(frame, (EndFrame, CancelFrame)):
            await self.stop()
            return
        if isinstance(frame, InterruptionFrame):
            if self._after_interruption:
                action, self._after_interruption = self._after_interruption, None
                self._awaiting_new_speech = True
                self._reply_timeout_task = asyncio.create_task(self._on_reply_timeout())
                await action()
            return

        # Track the student's turn even while paused, so a turn that ends
        # during a pause does not leave the flag stuck.
        if isinstance(frame, UserStartedSpeakingFrame):
            self._user_speaking = True
        elif isinstance(frame, UserStoppedSpeakingFrame):
            self._user_speaking = False

        if isinstance(frame, BotStartedSpeakingFrame):
            self._bot_speaking = True
            self._awaiting_new_speech = False
            self._cancel_reply_timeout()
            self._cancel_idle()
        elif isinstance(frame, BotStoppedSpeakingFrame):
            self._bot_speaking = False
            # An interruption stops the tutor while the student is still
            # talking; their UserStoppedSpeaking starts the countdown instead.
            if self._ready_to_count_down():
                self._schedule_idle(self._idle_secs)
        elif self.presentation.paused:
            # Mic input is muted while paused; ignore any stray user turn.
            return
        elif isinstance(frame, UserStartedSpeakingFrame):
            self._cancel_idle()
            self.presentation.on_user_spoke()
        elif isinstance(frame, UserStoppedSpeakingFrame):
            # Normally the tutor answers and BotStoppedSpeaking restarts the
            # flow. This fallback covers a reply that never comes.
            self._schedule_idle(self._no_reply_secs)

    def _tutor_audible(self) -> bool:
        return self._bot_speaking or self._client_playing

    def _ready_to_count_down(self) -> bool:
        return not (
            self.presentation.paused
            or self._user_speaking
            or self._awaiting_new_speech
            or self._tutor_audible()
        )

    def _requests_blocked(self) -> bool:
        """True while paused or while a UI request waits for its interruption."""
        return self.presentation.paused or self._after_interruption is not None

    async def _interrupt_then(self, action: Callable[[], Awaitable[None]]) -> None:
        # Acting only once the interruption is observed keeps it from
        # cancelling the response the action starts.
        self._after_interruption = action
        self._cancel_idle()
        await self._queue_frames([InterruptionWorkerFrame()])

    async def _jump(self, number: int, request: str | None) -> None:
        await self._perform(self.presentation.go_to(number), request)

    async def _put_question(self, question: str, request: str | None) -> None:
        logger.info(f"Typed question: {question}")
        await self._queue_frames(
            [LLMMessagesAppendFrame([{"role": "user", "content": question}], run_llm=True)]
        )
        await self._notify(self.snapshot(request))

    def _already_seen(self, frame: Frame) -> bool:
        if frame.id in self._seen_ids or frame.broadcast_sibling_id in self._seen_ids:
            return True
        self._seen_ids.append(frame.id)
        return False

    def _schedule_idle(self, delay: float) -> None:
        self._cancel_idle()
        self._idle_delay = delay
        self._idle_task = asyncio.create_task(self._on_idle(delay))

    def _cancel_idle(self) -> None:
        if self._idle_task and not self._idle_task.done():
            self._idle_task.cancel()
        self._idle_task = None
        self._idle_delay = None

    async def _on_idle(self, delay: float) -> None:
        await asyncio.sleep(delay)
        self._idle_task = None
        self._idle_delay = None
        await self._perform(self.presentation.on_bot_idle())

    def _cancel_reply_timeout(self) -> None:
        if self._reply_timeout_task and not self._reply_timeout_task.done():
            self._reply_timeout_task.cancel()
        self._reply_timeout_task = None

    async def _on_reply_timeout(self) -> None:
        await asyncio.sleep(self._reply_timeout_secs)
        self._reply_timeout_task = None
        logger.warning("The reply to a UI request never spoke; carrying on")
        self._awaiting_new_speech = False
        if self._ready_to_count_down():
            self._schedule_idle(self._idle_secs)

    async def _perform(self, action: Action | None, request: str | None = None) -> None:
        # A tool call or countdown already in flight can land after the end.
        if action is None or self._ended:
            return
        direction = self._direction_for(action)
        logger.info(f"Lesson action: {action}")
        await self._queue_frames(
            [
                LLMMessagesTransformFrame(
                    transform=partial(prompts.with_stage_direction, direction=direction),
                    run_llm=True,
                )
            ]
        )
        await self._notify(self.snapshot(request))

    def _direction_for(self, action: Action) -> str:
        match action:
            case Present(slide=n):
                return prompts.present_slide(self.deck[n - 1], len(self.deck))
            case ContinueSlide(slide=n):
                return prompts.continue_slide(self.deck[n - 1])
            case StartQna():
                return prompts.start_qna()
