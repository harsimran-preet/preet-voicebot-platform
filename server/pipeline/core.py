import os
import logging
import asyncio
from typing import Any

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask
from pipecat.pipeline.runner import PipelineRunner

# Import services
from pipecat.services.soniox.stt import SonioxSTTService, SonioxSTTSettings
from pipecat.services.soniox.tts import SonioxTTSService, SonioxTTSSettings

# Import subagent elements
from pipecat_subagents.bus import AsyncQueueBus, BusBridgeProcessor
from pipecat_subagents.runner import AgentRunner
from server.agents.registry_agent import RegistryAgent
import json

logger = logging.getLogger("pipecat")

async def run_voice_pipeline(transport: Any, webrtc_connection: Any = None) -> None:
    """
    Runs the multi-agent voice pipeline for a given transport.
    Sets up:
      1. Soniox multilingual STT
      2. Pluggable subagents (Gemini Router & OpenAI Support) linked via in-memory AsyncQueueBus
      3. Soniox multilingual TTS
    """
    logger.info("Initializing Pipecat Multi-Agent Voice Pipeline...")

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

    # 3. Soniox TTS Service
    tts = SonioxTTSService(
        api_key=soniox_key
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

    # 6. Instantiate Subagents dynamically from Registry
    runner = AgentRunner(bus=bus, handle_sigint=False)
    
    registry_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "agents", "registry.json")
    agents_config = []
    try:
        if os.path.exists(registry_path):
            with open(registry_path, "r") as f:
                agents_config = json.load(f)
        else:
            logger.warning(f"Registry config file not found at {registry_path}. Using default fallback.")
    except Exception as e:
        logger.error(f"Failed to load registry config: {e}", exc_info=True)

    if not agents_config:
        agents_config = [
            {
                "id": "router",
                "name": "Router Agent",
                "prompt": (
                    "You are the ROUTER agent for Preet Voicebot Platform.\n"
                    "Your ONLY tasks are:\n"
                    "1. Greet the user briefly if they just connected.\n"
                    "2. Identify what the user needs. They can need general conversation/smalltalk, "
                    "or specific customer support (technical assistance, account help, password reset).\n"
                    "3. If they ask a support-related question, call the tool 'handoff_to_support' immediately. "
                    "Do NOT try to answer support questions yourself!\n"
                    "4. Keep your responses extremely brief (1-2 sentences at most).\n"
                    "5. Always respond in the caller's detected language."
                ),
                "llm_provider": "gemini",
                "active_on_start": True,
                "tools": [
                    {
                        "name": "handoff_to_support",
                        "description": (
                            "Classification tool to hand off control to the Support Specialist. "
                            "Call this immediately when the user requests general support, account assistance, "
                            "password help, technical issues, or refund requests."
                        ),
                        "target_agent": "support"
                    }
                ]
            },
            {
                "id": "support",
                "name": "Support Specialist",
                "prompt": (
                    "You are the SUPPORT SPECIALIST for Preet Voicebot Platform.\n"
                    "Your ONLY task is to help the user with customer support issues, technical assistance, "
                    "and account troubleshooting.\n"
                    "Keep your responses extremely helpful, professional, and very brief (1-2 sentences at most).\n"
                    "Do NOT read out bullet points, lists, or markdown as you are speaking out loud.\n"
                    "If the user asks about billing, sales, or general topics unrelated to technical support, "
                    "or if the user says they are done, call the 'return_to_router' tool immediately to route them back.\n"
                    "Always respond in the caller's detected language."
                ),
                "llm_provider": "openai",
                "active_on_start": False,
                "tools": [
                    {
                        "name": "return_to_router",
                        "description": (
                            "Tool to return the conversation control back to the central Router. "
                            "Call this immediately when the user is done with support, or asks about sales, "
                            "billing, or other non-support topics."
                        ),
                        "target_agent": "router"
                    }
                ]
            }
        ]

    # 7. Create and register agents, coordinating dynamic active agent telemetry
    for cfg in agents_config:
        agent_id = cfg["id"]
        prompt = cfg["prompt"]
        provider = cfg["llm_provider"]
        tools_cfg = cfg.get("tools", [])
        active = cfg.get("active_on_start", False)
        
        agent = RegistryAgent(
            agent_id,
            prompt=prompt,
            provider=provider,
            tools_config=tools_cfg,
            bus=bus,
            active=active
        )
        await runner.add_agent(agent)
        
        # Telemetry activated event handler (sends agent ID and provider back to UI)
        def make_activation_handler(a_id=agent_id, a_prov=provider):
            async def on_activated(agent, args):
                logger.info(f"Agent '{a_id}' ({a_prov}) activated.")
                if webrtc_connection:
                    webrtc_connection.send_app_message({
                        "type": "active_agent",
                        "name": a_id,
                        "provider": a_prov
                    })
            return on_activated
            
        agent.add_event_handler("on_activated", make_activation_handler())

    # 8. Setup Transport Connection/Disconnection Events
    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info(f"Client connected: {client}")
        # Notify UI of initial active agent
        if webrtc_connection:
            webrtc_connection.send_app_message({"type": "active_agent", "name": "router"})

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info(f"Client disconnected: {client}")
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
