import pytest

from tutor.presentation import ContinueSlide, Mode, Present, Presentation, StartQna


def make(count: int = 3) -> Presentation:
    return Presentation(slide_count=count)


def test_start_presents_first_slide():
    p = make()
    assert p.start() == Present(1)
    assert p.mode is Mode.PRESENTING
    assert p.slide == 1


def test_start_is_idempotent():
    p = make()
    p.start()
    assert p.start() is None
    assert p.slide == 1


def test_idle_before_start_does_nothing():
    p = make()
    assert p.on_bot_idle() is None
    assert p.slide is None


def test_idle_advances_to_next_slide():
    p = make()
    p.start()
    assert p.on_bot_idle() == Present(2)
    assert p.slide == 2


def test_idle_after_user_question_continues_same_slide():
    p = make()
    p.start()
    p.on_user_spoke()
    assert p.on_bot_idle() == ContinueSlide(1)
    assert p.slide == 1
    # Once back on topic, the next idle moves on as normal.
    assert p.on_bot_idle() == Present(2)


def test_last_slide_is_presented_before_qna():
    p = make(count=2)
    p.start()
    assert p.on_bot_idle() == Present(2)
    assert p.mode is Mode.PRESENTING


def test_idle_after_last_slide_enters_qna_once():
    p = make(count=2)
    p.start()
    p.on_bot_idle()
    assert p.on_bot_idle() == StartQna()
    assert p.mode is Mode.QNA
    assert p.on_bot_idle() is None
    assert p.on_bot_idle() is None


def test_question_on_last_slide_finishes_slide_before_qna():
    p = make(count=1)
    p.start()
    p.on_user_spoke()
    assert p.on_bot_idle() == ContinueSlide(1)
    assert p.on_bot_idle() == StartQna()


def test_user_speech_in_qna_does_not_trigger_continue():
    p = make(count=1)
    p.start()
    p.on_bot_idle()
    p.on_user_spoke()
    assert p.on_bot_idle() is None
    assert p.mode is Mode.QNA


def test_go_to_from_qna_resumes_presenting():
    p = make(count=3)
    p.start()
    p.on_bot_idle()
    p.on_bot_idle()
    p.on_bot_idle()
    assert p.mode is Mode.QNA
    assert p.go_to(2) == Present(2)
    assert p.mode is Mode.PRESENTING
    assert p.on_bot_idle() == Present(3)
    assert p.on_bot_idle() == StartQna()


def test_go_to_clears_pending_question():
    p = make()
    p.start()
    p.on_user_spoke()
    p.go_to(3)
    assert p.on_bot_idle() == StartQna()


def test_go_to_before_start_starts_presentation():
    p = make()
    assert p.go_to(2) == Present(2)
    assert p.start() is None


@pytest.mark.parametrize("number", [0, 4, -1])
def test_go_to_rejects_out_of_range(number):
    p = make(count=3)
    p.start()
    with pytest.raises(ValueError):
        p.go_to(number)
    assert p.slide == 1


def test_rejects_empty_deck():
    with pytest.raises(ValueError):
        Presentation(slide_count=0)
