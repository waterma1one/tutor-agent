"""The websocket serializer, matched to what the browser client can read."""

from pipecat.frames.frames import Frame, InterruptionFrame
from pipecat.serializers.protobuf import ProtobufFrameSerializer


class WebClientSerializer(ProtobufFrameSerializer):
    """Protobuf, minus the frames the web client cannot decode.

    pipecat 1.11 sends interruptions as their own protobuf frame kind, which
    `@pipecat-ai/websocket-transport` 1.6 rejects with "Unknown frame kind".
    The client never needed it: it stops playback itself on the RTVI
    user-started-speaking message and before sending a UI ask or jump. So the
    frame is dropped here rather than logged as an error in the browser.
    """

    async def serialize(self, frame: Frame) -> str | bytes | None:
        if isinstance(frame, InterruptionFrame):
            return None
        return await super().serialize(frame)
