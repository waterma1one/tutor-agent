"""Pure presentation state machine.

Knows nothing about pipecat. Each event method returns the action the caller
should perform next (or None), which keeps the flow deterministic and testable.
Slide numbers are 1-based, matching what students and the UI see.
"""

from dataclasses import dataclass
from enum import StrEnum


class Mode(StrEnum):
    PRESENTING = "presenting"
    QNA = "qna"


@dataclass(frozen=True)
class Present:
    """Present a slide from the beginning."""

    slide: int


@dataclass(frozen=True)
class ContinueSlide:
    """A question was answered; pick the slide back up where it was left."""

    slide: int


@dataclass(frozen=True)
class StartQna:
    """The last slide is done; switch to open conversation."""


Action = Present | ContinueSlide | StartQna


class Presentation:
    def __init__(self, slide_count: int):
        if slide_count < 1:
            raise ValueError("A presentation needs at least one slide")
        self.slide_count = slide_count
        self.mode = Mode.PRESENTING
        self.slide: int | None = None
        self._question_pending = False
        self.paused = False

    @property
    def started(self) -> bool:
        return self.slide is not None

    def pause(self) -> bool:
        """Freeze the flow. Returns whether anything changed.

        Pausing is orthogonal to the mode, so resuming lands back exactly where
        the lesson was, including a question still waiting for its answer.
        """
        if not self.started or self.paused:
            return False
        self.paused = True
        return True

    def resume(self) -> bool:
        if not self.paused:
            return False
        self.paused = False
        return True

    def start(self) -> Action | None:
        if self.started:
            return None
        return self._present(1)

    def on_user_spoke(self) -> None:
        if self.started and not self.paused and self.mode is Mode.PRESENTING:
            self._question_pending = True

    def on_bot_idle(self) -> Action | None:
        """The tutor finished talking and nobody spoke for a while."""
        if not self.started or self.paused or self.mode is Mode.QNA:
            return None
        if self._question_pending:
            self._question_pending = False
            return ContinueSlide(self.slide)
        if self.slide < self.slide_count:
            return self._present(self.slide + 1)
        self.mode = Mode.QNA
        return StartQna()

    def go_to(self, number: int) -> Action:
        if not 1 <= number <= self.slide_count:
            raise ValueError(f"Slide {number} does not exist (1-{self.slide_count})")
        return self._present(number)

    def _present(self, number: int) -> Present:
        self.slide = number
        self.mode = Mode.PRESENTING
        self._question_pending = False
        return Present(number)
