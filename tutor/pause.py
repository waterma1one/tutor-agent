"""Holds the tutor's speech while the lesson is paused.

`PauseGate` sits right before the output transport. While paused it keeps every
downstream data and control frame (TTS audio, the text that goes with it, TTS
start/stop markers) in arrival order, and on resume pushes them on unchanged.
Speech therefore continues from the exact audio chunk where it stopped.

Audio already sent to the browser is paused there; see docs/NOTES.md.
"""

import asyncio

from pipecat.frames.frames import (
    EndFrame,
    Frame,
    InterruptionFrame,
    StopFrame,
    SystemFrame,
    UninterruptibleFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class PauseGate(FrameProcessor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._paused = False
        self._held: list[Frame] = []
        # Keeps a flush on resume from interleaving with frames that arrive
        # while it is running.
        self._lock = asyncio.Lock()

    @property
    def paused(self) -> bool:
        return self._paused

    @property
    def held_count(self) -> int:
        return len(self._held)

    async def pause(self) -> None:
        async with self._lock:
            self._paused = True

    async def resume(self) -> None:
        async with self._lock:
            await self._release()

    async def _release(self) -> None:
        held, self._held = self._held, []
        for frame in held:
            await self.push_frame(frame)
        self._paused = False

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if direction is FrameDirection.UPSTREAM:
            await self.push_frame(frame, direction)
            return

        async with self._lock:
            if isinstance(frame, (InterruptionFrame, EndFrame, StopFrame)):
                # Held speech is stale once the tutor is cut off or the session
                # ends. Frames pipecat marks uninterruptible (tool results) must
                # still reach the context.
                self._held = [f for f in self._held if isinstance(f, UninterruptibleFrame)]
                if not isinstance(frame, InterruptionFrame):
                    # The session is ending, so there is nothing to wait for.
                    await self._release()
                await self.push_frame(frame, direction)
            elif self._paused and not isinstance(frame, SystemFrame):
                self._held.append(frame)
            else:
                await self.push_frame(frame, direction)
