from pipecat.frames.frames import ErrorFrame, OutputTransportMessageFrame, TTSAudioRawFrame
from pipecat.services.openai.tts import OpenAITTSService

from tutor.captions import CaptionedTTSService


async def fake_run_tts(self, text, context_id):
    yield TTSAudioRawFrame(b"\x00\x00", 24000, 1, context_id=context_id)
    yield TTSAudioRawFrame(b"\x00\x00", 24000, 1, context_id=context_id)


async def collect(service, text):
    return [frame async for frame in service.run_tts(text, "ctx-1")]


async def test_caption_goes_out_before_the_sentence_audio(monkeypatch):
    monkeypatch.setattr(OpenAITTSService, "run_tts", fake_run_tts)
    service = CaptionedTTSService(
        api_key="test", settings=CaptionedTTSService.Settings(voice="coral")
    )

    frames = await collect(service, "Earthquakes shake the ground.")

    caption = frames[0]
    assert isinstance(caption, OutputTransportMessageFrame)
    assert caption.message == {
        "label": "rtvi-ai",
        "type": "server-message",
        "data": {"type": "caption", "text": "Earthquakes shake the ground."},
    }
    assert all(isinstance(frame, TTSAudioRawFrame) for frame in frames[1:])
    assert len(frames) == 3


async def test_blank_text_sends_no_caption(monkeypatch):
    monkeypatch.setattr(OpenAITTSService, "run_tts", fake_run_tts)
    service = CaptionedTTSService(
        api_key="test", settings=CaptionedTTSService.Settings(voice="coral")
    )

    frames = await collect(service, "   ")

    assert not any(isinstance(frame, OutputTransportMessageFrame) for frame in frames)


async def failing_run_tts(self, text, context_id):
    yield ErrorFrame(error="TTS failed")


async def test_sentence_that_fails_to_speak_sends_no_caption(monkeypatch):
    monkeypatch.setattr(OpenAITTSService, "run_tts", failing_run_tts)
    service = CaptionedTTSService(
        api_key="test", settings=CaptionedTTSService.Settings(voice="coral")
    )

    frames = await collect(service, "Earthquakes shake the ground.")

    assert [type(frame) for frame in frames] == [ErrorFrame]
