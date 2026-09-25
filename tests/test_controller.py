import asyncio
from types import SimpleNamespace

import pytest
from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    CancelFrame,
    EndFrame,
    InterruptionFrame,
    InterruptionWorkerFrame,
    LLMMessagesTransformFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.observers.base_observer import FramePushed
from pipecat.processors.frame_processor import FrameDirection

from tutor.controller import LessonController
from tutor.prompts import STAGE_MARKER
from tutor.slides import DECK

IDLE = 0.01


class FakeGate:
    def __init__(self):
        self.calls: list[str] = []

    async def pause(self):
        self.calls.append("pause")

    async def resume(self):
        self.calls.append("resume")


class Harness:
    def __init__(self, deck=DECK):
        self.queued: list = []
        self.notes: list[dict] = []
        self.gate = FakeGate()
        self.controller = LessonController(
            deck,
            queue_frames=self._queue,
            notify=self._notify,
            speech_gate=self.gate,
            idle_secs=IDLE,
            no_reply_secs=IDLE,
        )

    async def _queue(self, frames):
        self.queued.extend(frames)

    async def _notify(self, state):
        self.notes.append(state)

    async def push(self, frame, hops: int = 1):
        for _ in range(hops):
            await self.controller.on_push_frame(
                FramePushed(
                    source=None,
                    destination=None,
                    frame=frame,
                    direction=FrameDirection.DOWNSTREAM,
                    timestamp=0,
                )
            )

    def last_direction(self) -> str:
        frame = self.queued[-1]
        assert isinstance(frame, LLMMessagesTransformFrame)
        return frame.transform([])[-1]["content"]


async def settle():
    await asyncio.sleep(IDLE * 5)


async def test_start_presents_first_slide_and_notifies():
    h = Harness()
    await h.controller.start()
    assert h.last_direction().startswith(f"{STAGE_MARKER} Present slide 1")
    assert h.notes[-1] == {
        "type": "lesson-state",
        "mode": "presenting",
        "slide": 1,
        "total": 8,
        "paused": False,
        "request": None,
    }


async def test_bot_silence_advances_once_despite_repeated_hops():
    h = Harness()
    await h.controller.start()
    await h.push(BotStoppedSpeakingFrame(), hops=5)
    await settle()
    assert h.controller.presentation.slide == 2
    assert len(h.queued) == 2


async def test_sibling_frames_count_once():
    h = Harness()
    await h.controller.start()
    down, up = BotStoppedSpeakingFrame(), BotStoppedSpeakingFrame()
    up.broadcast_sibling_id = down.id
    await h.push(down)
    await h.push(up)
    await settle()
    assert h.controller.presentation.slide == 2


async def test_bot_speaking_again_cancels_pending_advance():
    h = Harness()
    await h.controller.start()
    await h.push(BotStoppedSpeakingFrame())
    await h.push(BotStartedSpeakingFrame())
    await settle()
    assert h.controller.presentation.slide == 1


async def test_user_question_then_silence_returns_to_same_slide():
    h = Harness()
    await h.controller.start()
    await h.push(UserStartedSpeakingFrame())
    await h.push(UserStoppedSpeakingFrame())
    await h.push(BotStoppedSpeakingFrame())
    await settle()
    assert h.controller.presentation.slide == 1
    assert "back to" in h.last_direction()


async def test_interrupted_tutor_waits_while_the_student_is_talking():
    h = Harness()
    await h.controller.start()
    await h.push(BotStartedSpeakingFrame())
    await h.push(UserStartedSpeakingFrame())
    # The interruption stops the tutor, but the student is still mid-sentence.
    await h.push(BotStoppedSpeakingFrame())
    await settle()
    assert len(h.queued) == 1


async def test_student_finishing_after_interruption_gets_one_follow_up():
    h = Harness()
    await h.controller.start()
    await h.push(BotStartedSpeakingFrame())
    await h.push(UserStartedSpeakingFrame())
    await h.push(BotStoppedSpeakingFrame())
    await h.push(UserStoppedSpeakingFrame())
    await settle()
    assert len(h.queued) == 2
    assert "back to" in h.last_direction()


async def test_student_turn_ending_during_pause_does_not_stall_the_lesson():
    h = Harness()
    await h.controller.start()
    await h.push(UserStartedSpeakingFrame())
    await h.controller.pause()
    await h.push(UserStoppedSpeakingFrame())
    await h.controller.resume()
    await h.push(BotStoppedSpeakingFrame())
    await settle()
    assert len(h.queued) == 2


async def test_go_to_slide_tool_defers_direction_until_context_updated():
    h = Harness()
    await h.controller.start()
    results = []

    async def result_callback(result, properties=None):
        results.append((result, properties))

    params = SimpleNamespace(arguments={"slide_number": 3}, result_callback=result_callback)
    await h.controller.handle_go_to_slide(params)

    result, properties = results[0]
    assert result == {"ok": True, "slide": 3}
    assert properties.run_llm is False
    assert len(h.queued) == 1  # nothing queued until the tool result lands

    await properties.on_context_updated()
    assert h.last_direction().startswith(f"{STAGE_MARKER} Present slide 3")
    assert h.notes[-1]["slide"] == 3


@pytest.mark.parametrize("bad", [0, 99, "abc", None])
async def test_go_to_slide_tool_reports_invalid_slide(bad):
    h = Harness()
    await h.controller.start()
    results = []

    async def result_callback(result, properties=None):
        results.append(result)

    params = SimpleNamespace(arguments={"slide_number": bad}, result_callback=result_callback)
    await h.controller.handle_go_to_slide(params)
    assert results[0]["ok"] is False
    assert h.controller.presentation.slide == 1


async def test_pause_holds_speech_cancels_advance_and_notifies():
    h = Harness()
    await h.controller.start()
    await h.push(BotStoppedSpeakingFrame())
    await h.controller.pause()
    await settle()
    assert h.controller.presentation.slide == 1
    assert h.gate.calls == ["pause"]
    assert h.notes[-1]["paused"] is True


async def test_bot_stopping_while_paused_does_not_advance():
    h = Harness()
    await h.controller.start()
    await h.push(BotStartedSpeakingFrame())
    await h.controller.pause()
    await h.push(BotStoppedSpeakingFrame())
    await settle()
    assert h.controller.presentation.slide == 1


async def test_resume_while_silent_restarts_the_idle_timer():
    h = Harness()
    await h.controller.start()
    await h.push(BotStoppedSpeakingFrame())
    await h.controller.pause()
    await h.controller.resume()
    await settle()
    assert h.gate.calls == ["pause", "resume"]
    assert h.notes[-1]["paused"] is False
    assert h.controller.presentation.slide == 2


async def test_resume_mid_speech_waits_for_the_tutor_to_finish():
    h = Harness()
    await h.controller.start()
    await h.push(BotStartedSpeakingFrame())
    await h.controller.pause()
    await h.controller.resume()
    await settle()
    assert h.controller.presentation.slide == 1


async def test_user_speech_while_paused_is_ignored():
    h = Harness()
    await h.controller.start()
    await h.controller.pause()
    await h.push(UserStartedSpeakingFrame())
    await h.push(UserStoppedSpeakingFrame())
    await h.controller.resume()
    await h.push(BotStoppedSpeakingFrame())
    await settle()
    assert h.controller.presentation.slide == 2


async def test_resume_mid_question_waits_for_the_student_to_finish():
    h = Harness()
    await h.controller.start()
    await h.push(BotStoppedSpeakingFrame())
    await h.push(UserStartedSpeakingFrame())
    await h.controller.pause()
    await h.controller.resume()
    await settle()
    # The question is still open, so the tutor must not talk over it.
    assert len(h.queued) == 1

    await h.push(UserStoppedSpeakingFrame())
    await settle()
    assert "back to" in h.last_direction()


async def test_repeated_pause_and_resume_touch_the_gate_once():
    h = Harness()
    await h.controller.start()
    await h.controller.pause()
    await h.controller.pause()
    await h.controller.resume()
    await h.controller.resume()
    assert h.gate.calls == ["pause", "resume"]
    assert [n["paused"] for n in h.notes[1:]] == [True, True, False, False]


async def test_resume_restarts_the_timer_that_was_pending():
    h = Harness()
    h.controller._no_reply_secs = IDLE * 20
    await h.controller.start()
    await h.push(UserStartedSpeakingFrame())
    await h.push(UserStoppedSpeakingFrame())
    await h.controller.pause()
    await h.controller.resume()
    await settle()
    # The long wait for the tutor's reply survives the pause; the short idle
    # delay would re-ask the LLM while the first answer is still coming.
    assert len(h.queued) == 1


async def test_ignored_pause_still_reports_state():
    h = Harness()
    await h.controller.pause()
    assert h.gate.calls == []
    assert h.notes == [h.controller.snapshot()]


async def test_frames_after_cancel_do_not_move_the_lesson():
    h = Harness()
    await h.controller.start()
    await h.push(CancelFrame())
    await h.push(BotStoppedSpeakingFrame())
    await settle()
    assert len(h.queued) == 1


async def test_resume_after_end_does_nothing():
    h = Harness()
    await h.controller.start()
    await h.push(BotStoppedSpeakingFrame())
    await h.controller.pause()
    await h.push(EndFrame())
    await h.controller.resume()
    await settle()
    assert len(h.queued) == 1
    assert h.gate.calls == ["pause"]


async def test_stop_cancels_the_pending_countdown():
    h = Harness()
    await h.controller.start()
    await h.push(BotStoppedSpeakingFrame())
    await h.controller.stop()
    await settle()
    assert len(h.queued) == 1


async def test_waits_for_the_student_to_hear_the_end_before_advancing():
    h = Harness()
    await h.controller.start()
    await h.controller.on_playback(True)
    await h.push(BotStartedSpeakingFrame())
    # The server has sent everything, but the browser is still playing it.
    await h.push(BotStoppedSpeakingFrame())
    await settle()
    assert h.controller.presentation.slide == 1

    await h.controller.on_playback(False)
    await settle()
    assert h.controller.presentation.slide == 2


async def test_playback_gap_mid_speech_does_not_advance():
    h = Harness()
    await h.controller.start()
    await h.controller.on_playback(True)
    await h.push(BotStartedSpeakingFrame())
    await h.controller.on_playback(False)
    await settle()
    assert h.controller.presentation.slide == 1

    # Browser already drained when the server finishes, so count down now.
    await h.push(BotStoppedSpeakingFrame())
    await settle()
    assert h.controller.presentation.slide == 2


async def test_resume_with_audio_still_queued_waits_for_playback():
    h = Harness()
    await h.controller.start()
    await h.controller.on_playback(True)
    await h.push(BotStartedSpeakingFrame())
    await h.controller.pause()
    await h.push(BotStoppedSpeakingFrame())
    await h.controller.resume()
    await settle()
    assert h.controller.presentation.slide == 1

    await h.controller.on_playback(False)
    await settle()
    assert h.controller.presentation.slide == 2


async def test_playback_ending_while_paused_counts_down_on_resume():
    h = Harness()
    await h.controller.start()
    await h.controller.on_playback(True)
    await h.push(BotStartedSpeakingFrame())
    await h.push(BotStoppedSpeakingFrame())
    await h.controller.pause()
    await h.controller.on_playback(False)
    await settle()
    assert h.controller.presentation.slide == 1

    await h.controller.resume()
    await settle()
    assert h.controller.presentation.slide == 2


async def test_playback_stopped_by_an_interruption_waits_for_the_student():
    h = Harness()
    await h.controller.start()
    await h.controller.on_playback(True)
    await h.push(BotStartedSpeakingFrame())
    await h.push(UserStartedSpeakingFrame())
    await h.push(BotStoppedSpeakingFrame())
    await h.controller.on_playback(False)
    await settle()
    assert len(h.queued) == 1


async def test_playback_reports_after_stop_are_ignored():
    h = Harness()
    await h.controller.start()
    await h.controller.on_playback(True)
    await h.push(BotStoppedSpeakingFrame())
    await h.controller.stop()
    await h.controller.on_playback(False)
    await settle()
    assert len(h.queued) == 1


async def test_student_jump_interrupts_then_presents_the_slide():
    h = Harness()
    await h.controller.start()
    await h.push(BotStartedSpeakingFrame())
    await h.controller.request_slide(4)
    assert isinstance(h.queued[-1], InterruptionWorkerFrame)

    await h.push(InterruptionFrame(), hops=3)
    assert h.last_direction().startswith(f"{STAGE_MARKER} Present slide 4")
    assert h.notes[-1]["slide"] == 4


async def test_interrupted_speech_ending_does_not_skip_the_jumped_slide():
    h = Harness()
    await h.controller.start()
    await h.push(BotStartedSpeakingFrame())
    await h.controller.request_slide(4)
    await h.push(InterruptionFrame())
    await h.push(BotStoppedSpeakingFrame())
    await h.controller.on_playback(False)
    await settle()
    assert h.controller.presentation.slide == 4

    await h.push(BotStartedSpeakingFrame())
    await h.push(BotStoppedSpeakingFrame())
    await settle()
    assert h.controller.presentation.slide == 5


async def test_interruption_without_a_jump_changes_nothing():
    h = Harness()
    await h.controller.start()
    await h.push(InterruptionFrame())
    assert len(h.queued) == 1


async def test_jump_while_paused_is_refused():
    h = Harness()
    await h.controller.start()
    await h.controller.pause()
    await h.controller.request_slide(4)
    await h.push(InterruptionFrame())
    assert len(h.queued) == 1
    assert h.notes[-1]["slide"] == 1


async def test_jump_to_a_missing_slide_is_refused():
    h = Harness()
    await h.controller.start()
    await h.controller.request_slide(99)
    assert len(h.queued) == 1
    assert h.notes[-1]["slide"] == 1


async def test_lesson_state_echoes_the_request_it_answers():
    h = Harness()
    await h.controller.start()
    assert h.notes[-1]["request"] is None
    await h.controller.pause(request="p1")
    assert h.notes[-1]["request"] == "p1"
    await h.controller.resume(request="r1")
    assert h.notes[-1] == {**h.notes[-1], "request": "r1", "paused": False}
    await h.controller.request_slide(3, request="g1")
    assert h.notes[-1]["request"] == "g1"
