"""Builds and runs the voice pipeline for one classroom session."""

import os

from loguru import logger
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.serializers.protobuf import ProtobufFrameSerializer
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.openai.stt import OpenAIRealtimeSTTService
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams, FastAPIWebsocketTransport

from tutor import prompts
from tutor.captions import CaptionedTTSService
from tutor.controller import LessonController
from tutor.pause import MuteWhilePaused, PauseGate
from tutor.slides import DECK

LLM_MODEL = os.getenv("TUTOR_LLM_MODEL", "gpt-4o")
TTS_VOICE = os.getenv("TUTOR_TTS_VOICE", "coral")
# Every sentence is a separate TTS request, so the style has to pin the voice down
# tightly or its pitch and energy wander from one request to the next.
TTS_STYLE = (
    "Voice: one warm primary school teacher, the same person in every sentence. "
    "Pitch: mid-range and steady; do not rise or drop between sentences. "
    "Pacing: relaxed and even, about the same speed throughout, with short natural pauses "
    "at commas and full stops. "
    "Energy: gently enthusiastic and constant; never excited, dramatic, whispery or flat. "
    "Tone: friendly and reassuring, even when describing dangerous events. "
    "Pronunciation: clear and unhurried, for children listening in a classroom."
)

GO_TO_SLIDE = FunctionSchema(
    name="go_to_slide",
    description=(
        "Jump to a slide when a student asks to go back to, repeat, or skip to part of "
        "the lesson. Presentation continues from that slide."
    ),
    properties={
        "slide_number": {
            "type": "integer",
            "minimum": 1,
            "maximum": len(DECK),
            "description": "The slide to present, from the lesson outline.",
        }
    },
    required=["slide_number"],
)


async def run_bot(websocket) -> None:
    api_key = os.environ["OPENAI_API_KEY"]

    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            serializer=ProtobufFrameSerializer(),
        ),
    )
    stt = OpenAIRealtimeSTTService(
        api_key=api_key,
        settings=OpenAIRealtimeSTTService.Settings(model="gpt-4o-transcribe"),
    )
    llm = OpenAILLMService(api_key=api_key, settings=OpenAILLMService.Settings(model=LLM_MODEL))
    tts = CaptionedTTSService(
        api_key=api_key,
        settings=CaptionedTTSService.Settings(
            model="gpt-4o-mini-tts", voice=TTS_VOICE, instructions=TTS_STYLE
        ),
    )

    context = LLMContext(
        messages=[{"role": "system", "content": prompts.base_prompt(DECK)}],
        tools=ToolsSchema(standard_tools=[GO_TO_SLIDE]),
    )
    # Strict VAD so classroom noise is not mistaken for a question.
    vad = SileroVADAnalyzer(
        params=VADParams(confidence=0.85, start_secs=0.45, stop_secs=0.35, min_volume=0.7)
    )

    # The task and controller reference each other, so the controller gets
    # thin callbacks that resolve the task at call time.
    task: PipelineTask

    async def queue_frames(frames):
        await task.queue_frames(frames)

    async def notify(state: dict):
        await task.rtvi.send_server_message(state)

    gate = PauseGate()
    controller = LessonController(
        DECK, queue_frames=queue_frames, notify=notify, speech_gate=gate
    )
    llm.register_function("go_to_slide", controller.handle_go_to_slide)

    aggregators = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=vad,
            user_mute_strategies=[MuteWhilePaused(lambda: controller.presentation.paused)],
        ),
    )

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            aggregators.user(),
            llm,
            tts,
            gate,
            transport.output(),
            aggregators.assistant(),
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
        observers=[controller],
    )

    @task.rtvi.event_handler("on_client_ready")
    async def on_client_ready(rtvi):
        logger.info("Client ready, starting lesson")
        await controller.start()

    @task.rtvi.event_handler("on_client_message")
    async def on_client_message(rtvi, message):
        data = message.data if isinstance(message.data, dict) else {}
        # The client tags requests so it can match the lesson-state reply.
        request = data.get("request")
        match message.type:
            case "pause":
                await controller.pause(request)
            case "resume":
                await controller.resume(request)
            case "go-to-slide":
                try:
                    number = int(data.get("slide"))
                except (TypeError, ValueError):
                    logger.warning(f"Ignoring go-to-slide without a slide number: {data}")
                    return
                await controller.request_slide(number, request)
            case "ask":
                await controller.ask(data.get("text"), request)
            case "playback-started":
                await controller.on_playback(True)
            case "playback-idle":
                await controller.on_playback(False)
            case _:
                logger.warning(f"Ignoring unknown client message: {message.type}")

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Client disconnected")
        await controller.stop()
        await task.cancel()

    await PipelineRunner(handle_sigint=False).run(task)
