from pipecat.frames.frames import InterruptionFrame, OutputAudioRawFrame

from tutor.serializer import WebClientSerializer


async def test_interruptions_are_not_sent_to_the_browser():
    assert await WebClientSerializer().serialize(InterruptionFrame()) is None


async def test_audio_is_still_sent():
    frame = OutputAudioRawFrame(audio=b"\x00\x00" * 160, sample_rate=24000, num_channels=1)
    assert isinstance(await WebClientSerializer().serialize(frame), bytes)
