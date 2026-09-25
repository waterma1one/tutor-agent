"""Captions sent with each sentence's audio instead of after it."""

from collections.abc import AsyncGenerator

import pipecat.processors.frameworks.rtvi.models as RTVI
from pipecat.frames.frames import Frame, OutputTransportMessageFrame
from pipecat.services.openai.tts import OpenAITTSService


class CaptionedTTSService(OpenAITTSService):
    """OpenAI TTS that sends each sentence's text as a caption ahead of its audio.

    OpenAI TTS has no word timestamps, so pipecat queues a sentence's TTSTextFrame
    behind all of its audio and the client's `bot-tts-text` arrives once the sentence
    has finished playing. A non-urgent transport message yielded from `run_tts` joins
    the same audio context, and the output transport sends it in order with the audio,
    right before the sentence. Audio goes out at twice real time, so the browser still
    holds each caption until its sentence plays (frontend `captionQueue.ts`). Being a
    data frame, it is also held by the PauseGate while the lesson is paused.
    """

    async def run_tts(self, text: str, context_id: str) -> AsyncGenerator[Frame, None]:
        if text.strip():
            caption = RTVI.ServerMessage(data={"type": "caption", "text": text.strip()})
            yield OutputTransportMessageFrame(message=caption.model_dump(exclude_none=True))
        async for frame in super().run_tts(text, context_id):
            yield frame
