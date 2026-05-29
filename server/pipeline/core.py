import os
import logging
from typing import Any

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask
from pipecat.pipeline.runner import PipelineRunner
from pipecat.processors.aggregators.llm_context import LLMContext, LLMContextMessage
from pipecat.processors.aggregators.llm_response_universal import (
    LLMUserAggregator,
    LLMAssistantAggregator,
)

# Import services
from pipecat.services.soniox.stt import SonioxSTTService, SonioxSTTSettings
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport, TransportParams

# Import LLM adapter
from server.pipeline.llm_adapter import get_llm_service

logger = logging.getLogger("pipecat")

async def run_voice_pipeline(webrtc_connection: Any) -> None:
    """
    Runs the voice pipeline for a given WebRTC connection.
    This sets up:
      1. WebRTC transport (inbound/outbound audio)
      2. Soniox multilingual STT
      3. Pluggable OpenAI/Gemini LLM
      4. Cartesia high-fidelity TTS
    """
    logger.info("Initializing Pipecat Voice Pipeline...")

    # 1. Transport Parameters & Transport
    transport_params = TransportParams(
        audio_out_enabled=True,
        audio_in_enabled=True,
    )
    transport = SmallWebRTCTransport(
        webrtc_connection=webrtc_connection,
        params=transport_params
    )

    # 2. Soniox Multilingual STT Service
    soniox_key = os.getenv("SONIOX_API_KEY")
    if not soniox_key:
        raise ValueError("SONIOX_API_KEY environment variable is not set")
    
    stt_settings = SonioxSTTSettings(
        model="stt-rt-v4",
        enable_language_identification=True,
    )
    stt = SonioxSTTService(
        api_key=soniox_key,
        settings=stt_settings,
        vad_force_turn_endpoint=True
    )

    # 3. Cartesia TTS Service
    cartesia_key = os.getenv("CARTESIA_API_KEY")
    if not cartesia_key:
        raise ValueError("CARTESIA_API_KEY environment variable is not set")
    
    # a0e9987c-abaf-4752-bd35-40671e7955ee is a high-quality friendly female voice (Barbra)
    cartesia_voice = os.getenv("CARTESIA_VOICE_ID", "a0e9987c-abaf-4752-bd35-40671e7955ee")
    tts = CartesiaTTSService(
        api_key=cartesia_key,
        voice_id=cartesia_voice,
        model="sonic-english"
    )

    # 4. Pluggable LLM Adapter
    system_instruction = (
        "You are a friendly, helpful AI voice assistant for Preet Voicebot Platform.\n"
        "You understand over 60 languages. Always reply in the same language the caller speaks in.\n"
        "Keep your answers very brief and conversational (1-2 sentences at most).\n"
        "Avoid bullet points, lists, or markdown formatting, as you are speaking out loud.\n"
        "If the caller is silent or greets you, greet them warmly and ask how you can help."
    )
    
    # Instantiate the LLM service dynamically based on the .env config
    provider = os.getenv("ROUTER_LLM", "gemini")
    logger.info(f"Using selectable LLM provider: {provider}")
    llm = get_llm_service(
        provider=provider,
        system_instruction=system_instruction
    )

    # 5. LLM User and Assistant Context Aggregators
    # Standard conversation context starting with system instructions
    messages = [
        LLMContextMessage(role="system", content=system_instruction)
    ]
    context = LLMContext(messages=messages)
    
    user_aggregator = LLMUserAggregator(context)
    assistant_aggregator = LLMAssistantAggregator(context)

    # 6. Pipeline Assembly
    # Flow: Audio In -> STT -> Aggregator -> LLM -> TTS -> Audio Out -> Aggregator (Assistant)
    pipeline = Pipeline([
        transport.input(),
        stt,
        user_aggregator,
        llm,
        tts,
        transport.output(),
        assistant_aggregator
    ])

    # 7. Pipeline Runner & Task execution
    task = PipelineTask(pipeline)
    runner = PipelineRunner()

    # Register basic transport events for logging
    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info(f"WebRTC client connected: {client}")
        # Automatically greet the user upon connection
        await task.queue_frames([LLMContextMessage(role="user", content="Hello!").to_frame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info(f"WebRTC client disconnected: {client}")
        await task.cancel()

    try:
        logger.info("Starting Pipecat pipeline runner...")
        await runner.run(task)
    except Exception as e:
        logger.error(f"Error in running Pipecat pipeline: {e}", exc_info=True)
    finally:
        logger.info("Voice pipeline finished and cleaned up.")
