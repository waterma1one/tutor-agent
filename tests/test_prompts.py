from tutor.prompts import (
    STAGE_MARKER,
    base_prompt,
    continue_slide,
    present_slide,
    with_stage_direction,
)
from tutor.slides import DECK


def test_stage_direction_replaces_previous_one():
    messages = [
        {"role": "system", "content": "base"},
        {"role": "system", "content": present_slide(DECK[0], len(DECK))},
        {"role": "assistant", "content": "Hello class"},
    ]
    result = with_stage_direction(messages, continue_slide(DECK[0]))

    directions = [m for m in result if m["content"].startswith(STAGE_MARKER)]
    assert len(directions) == 1
    assert result[-1]["content"] == continue_slide(DECK[0])


def test_stage_direction_keeps_conversation_and_base_prompt():
    messages = [
        {"role": "system", "content": "base"},
        {"role": "user", "content": f"{STAGE_MARKER} not from system"},
        {"role": "assistant", "content": "Hello class"},
    ]
    result = with_stage_direction(messages, "next")
    assert result[:3] == messages


def test_stage_direction_does_not_mutate_input():
    messages = [{"role": "system", "content": present_slide(DECK[0], len(DECK))}]
    with_stage_direction(messages, "next")
    assert len(messages) == 1


def test_base_prompt_lists_every_slide():
    prompt = base_prompt(DECK)
    for slide in DECK:
        assert f"{slide.number}. {slide.title}" in prompt


def test_first_slide_greets_later_slides_transition():
    assert "greeting" in present_slide(DECK[0], len(DECK))
    assert "transition" in present_slide(DECK[1], len(DECK))
