import asyncio

import pytest
from pipecat.frames.frames import (
    CancelFrame,
    EndFrame,
    FunctionCallResultFrame,
    InterruptionFrame,
    OutputTransportMessageUrgentFrame,
    TTSAudioRawFrame,
    TTSStoppedFrame,
    TTSTextFrame,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.tests.utils import SleepFrame, run_test

from tutor.pause import PauseGate

DOWN = FrameDirection.DOWNSTREAM
UP = FrameDirection.UPSTREAM


class RecordingGate(PauseGate):
    """PauseGate that records what it pushes instead of linking to a pipeline."""

    def __init__(self):
        super().__init__()
        self.pushed: list = []

    async def push_frame(self, frame, direction=DOWN):
        self.pushed.append((frame, direction))


def audio(n: int) -> TTSAudioRawFrame:
    return TTSAudioRawFrame(audio=bytes([n]) * 4, sample_rate=24000, num_channels=1)


def tool_result() -> FunctionCallResultFrame:
    return FunctionCallResultFrame(
        function_name="go_to_slide", tool_call_id="1", arguments={}, result={"ok": True}
    )


@pytest.fixture
def gate():
    return RecordingGate()


def pushed_frames(gate):
    return [f for f, _ in gate.pushed]


async def test_passes_frames_through_when_not_paused(gate):
    frames = [audio(1), TTSTextFrame("Hi", aggregated_by="word"), TTSStoppedFrame()]
    for f in frames:
        await gate.process_frame(f, DOWN)
    assert pushed_frames(gate) == frames


async def test_holds_speech_while_paused_and_flushes_in_order(gate):
    await gate.process_frame(first := audio(1), DOWN)
    await gate.pause()
    held = [audio(2), TTSTextFrame("volcano", aggregated_by="word"), audio(3), TTSStoppedFrame()]
    for f in held:
        await gate.process_frame(f, DOWN)
    assert pushed_frames(gate) == [first]
    assert gate.held_count == 4

    await gate.resume()
    assert pushed_frames(gate) == [first, *held]
    assert gate.held_count == 0
    assert not gate.paused


async def test_system_frames_pass_while_paused(gate):
    await gate.pause()
    msg = OutputTransportMessageUrgentFrame(message={"type": "lesson-state"})
    await gate.process_frame(msg, DOWN)
    assert pushed_frames(gate) == [msg]


async def test_upstream_frames_pass_while_paused(gate):
    await gate.pause()
    frame = audio(1)
    await gate.process_frame(frame, UP)
    assert gate.pushed == [(frame, UP)]


async def test_interruption_drops_held_speech_but_keeps_tool_results():
    # Interruptions need a running task manager, so use a real test pipeline.
    gate = PauseGate()
    await gate.pause()
    # CancelFrame stops the test pipeline without touching held frames,
    # unlike EndFrame, which would drop held speech on its own.
    down, _ = await asyncio.wait_for(
        run_test(
            gate,
            frames_to_send=[
                audio(1),
                tool_result(),
                audio(2),
                # Let the data frames reach the gate before the system frames,
                # which would otherwise overtake them.
                SleepFrame(0.05),
                InterruptionFrame(),
                SleepFrame(0.05),
                CancelFrame(),
            ],
            send_end_frame=False,
        ),
        timeout=5,
    )
    assert InterruptionFrame in [type(f) for f in down]
    assert gate.paused
    assert gate.held_count == 1


async def test_end_while_paused_releases_tool_results_and_ends(gate):
    await gate.pause()
    result = tool_result()
    for f in [audio(1), result]:
        await gate.process_frame(f, DOWN)
    end = EndFrame()
    await gate.process_frame(end, DOWN)
    assert pushed_frames(gate) == [result, end]
    assert not gate.paused


async def test_resume_without_pause_is_harmless(gate):
    await gate.resume()
    assert gate.pushed == []
    assert not gate.paused
