import os
import logging
import asyncio
from typing import Any

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask
from pipecat.pipeline.runner import PipelineRunner

# Import services
from pipecat.services.soniox.stt import SonioxSTTService, SonioxSTTSettings
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport, TransportParams

# Import subagent elements
from pipecat_subagents.bus import AsyncQueueBus, BusBridgeProcessor
from pipecat_subagents.runner import AgentRunner
from server.agents.router import RouterAgent
from server.agents.support import SupportAgent

logger = logging.getLogger("pipecat")

async def run_voice_pipeline(webrtc_connection: Any) -> None:
    """
    Runs the multi-agent voice pipeline for a given WebRTC connection.
    Sets up:
      1. WebRTC transport (inbound/outbound audio)
      2. Soniox multilingual STT
      3. Pluggable subagents (Gemini Router & OpenAI Support) linked via in-memory AsyncQueueBus
      4. Cartesia high-fidelity TTS
    """
    logger.info("Initializing Pipecat Multi-Agent Voice Pipeline...")

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
    
    cartesia_voice = os.getenv("CARTESIA_VOICE_ID", "a0e9987c-abaf-4752-bd35-40671e7955ee")
    tts = CartesiaTTSService(
        api_key=cartesia_key,
        voice_id=cartesia_voice,
        model="sonic-english"
    )

    # 4. Multi-Agent Bus and Bridge Processor
    # In-memory async queue bus for fast, local inter-agent turn handoffs
    bus = AsyncQueueBus()
    bridge = BusBridgeProcessor(bus=bus, agent_name="main")

    # 5. Core Pipeline Assembly (Drop-in Bridge replaces single LLM)
    pipeline = Pipeline([
        transport.input(),
        stt,
        bridge,
        tts,
        transport.output()
    ])

    task = PipelineTask(pipeline)
    pipeline_runner = PipelineRunner()

    # 6. Instantiate Subagents and AgentRunner
    runner = AgentRunner(bus=bus, handle_sigint=False)
    
    # Router starts active, Support starts idle
    router = RouterAgent("router", bus=bus, active=True)
    support = SupportAgent("support", bus=bus, active=False)
    
    runner.add_agent(router)
    runner.add_agent(support)

    # 7. Coordinate Active Agent Telemetry
    # When an agent activates, notify the React browser client instantly
    @router.event_handler("on_activated")
    async def on_router_active(agent, args):
        logger.info("Router Agent activated.")
        await webrtc_connection.send_app_message({"type": "active_agent", "name": "router"})

    @support.event_handler("on_activated")
    async def on_support_active(agent, args):
        logger.info("Support Agent activated.")
        await webrtc_connection.send_app_message({"type": "active_agent", "name": "support"})

    # 8. Setup Transport Connection/Disconnection Events
    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info(f"WebRTC client connected: {client}")
        # Notify UI of initial active agent
        await webrtc_connection.send_app_message({"type": "active_agent", "name": "router"})

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info(f"WebRTC client disconnected: {client}")
        # Tear down both loops cleanly
        await task.cancel()
        await runner.end()

    # 9. Concurrently run both the main transport pipeline and subagent runners
    try:
        logger.info("Running pipeline and subagent loops concurrently...")
        await asyncio.gather(
            pipeline_runner.run(task),
            runner.run()
        )
    except Exception as e:
        logger.error(f"Error in multi-agent pipeline execution: {e}", exc_info=True)
    finally:
        logger.info("Multi-agent voice pipeline finished and cleaned up.")
