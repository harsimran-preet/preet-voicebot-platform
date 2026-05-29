import os
import logging
import asyncio
import json
from dotenv import load_dotenv

# Load env variables before other imports
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport, TransportParams
from pipecat.transports.websocket.fastapi import FastAPIWebsocketTransport, FastAPIWebsocketParams
from pipecat.serializers.plivo import PlivoFrameSerializer
from server.pipeline.core import run_voice_pipeline

# Configure logging
logging.basicConfig(level=logging.INFO)
# Disable extremely verbose loggers
logging.getLogger("aiortc").setLevel(logging.WARNING)
logging.getLogger("websockets").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

logger = logging.getLogger("preet-voicebot-server")

app = FastAPI(title="Preet Voicebot Platform Backend", version="1.0.0")

# Enable CORS for local Vite development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from pydantic import Field

class WebRTCOffer(BaseModel):
    sdp: str
    type: str

class ToolConfig(BaseModel):
    name: str = Field(..., description="Name of the tool function")
    description: str = Field(..., description="Function docstring description")
    target_agent: str = Field(..., description="Target subagent ID to route control to")

class AgentConfig(BaseModel):
    id: str = Field(..., description="Unique ID of the agent")
    name: str = Field(..., description="Human readable name of the agent")
    prompt: str = Field(..., description="System instructions/prompt for the agent")
    llm_provider: str = Field("gemini", description="LLM provider: gemini or openai")
    active_on_start: bool = Field(False, description="Whether this agent is active at connection start")
    tools: list[ToolConfig] = Field(default=[], description="Handoff tools registered with this agent")

REGISTRY_PATH = os.path.join(os.path.dirname(__file__), "agents", "registry.json")

def init_registry_file():
    """Generates a default registry.json if it is missing."""
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    if not os.path.exists(REGISTRY_PATH):
        logger.info(f"Registry file not found at {REGISTRY_PATH}. Creating default config...")
        default_config = [
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
        with open(REGISTRY_PATH, "w") as f:
            json.dump(default_config, f, indent=2)

init_registry_file()

@app.get("/health")
@app.get("/api/health")
def health_check():
    """
    Simple liveness and readiness probe.
    """
    return {
        "status": "healthy",
        "pipecat_version": "1.3.0",
        "router_llm": os.getenv("ROUTER_LLM", "gemini")
    }

@app.get("/api/agents")
def get_agents():
    """
    List all configured subagents in the registry.
    """
    try:
        if os.path.exists(REGISTRY_PATH):
            with open(REGISTRY_PATH, "r") as f:
                return json.load(f)
        return []
    except Exception as e:
        logger.error(f"Error reading registry: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to read registry: {str(e)}")

@app.post("/api/agents")
def create_or_update_agent(agent: AgentConfig):
    """
    Create a new subagent or update an existing one in the registry.
    """
    try:
        agents = []
        if os.path.exists(REGISTRY_PATH):
            with open(REGISTRY_PATH, "r") as f:
                agents = json.load(f)
                
        # Find and replace if exists, or append if new
        updated = False
        for idx, a in enumerate(agents):
            if a["id"] == agent.id:
                agents[idx] = agent.model_dump()
                updated = True
                break
                
        if not updated:
            agents.append(agent.model_dump())
            
        with open(REGISTRY_PATH, "w") as f:
            json.dump(agents, f, indent=2)
            
        logger.info(f"Successfully saved agent '{agent.id}' to registry")
        return {"status": "success", "message": f"Agent '{agent.id}' saved successfully."}
    except Exception as e:
        logger.error(f"Error saving agent: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save agent: {str(e)}")

@app.delete("/api/agents/{agent_id}")
def delete_agent(agent_id: str):
    """
    Delete a subagent from the registry.
    Note: The core router agent cannot be deleted.
    """
    if agent_id == "router":
        raise HTTPException(status_code=400, detail="The core Router agent cannot be deleted.")
        
    try:
        agents = []
        if os.path.exists(REGISTRY_PATH):
            with open(REGISTRY_PATH, "r") as f:
                agents = json.load(f)
                
        # Filter out the agent
        filtered_agents = [a for a in agents if a["id"] != agent_id]
        
        if len(filtered_agents) == len(agents):
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found.")
            
        with open(REGISTRY_PATH, "w") as f:
            json.dump(filtered_agents, f, indent=2)
            
        logger.info(f"Successfully deleted agent '{agent_id}' from registry")
        return {"status": "success", "message": f"Agent '{agent_id}' deleted successfully."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting agent: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete agent: {str(e)}")


@app.post("/api/offer")
async def webrtc_offer(offer: WebRTCOffer, background_tasks: BackgroundTasks):
    """
    WebRTC Signaling Endpoint.
    Accepts the SDP offer from the browser console, establishes a SmallWebRTCConnection,
    generates the SDP answer, and kicks off the Pipecat voice pipeline in the background.
    """
    logger.info("Received WebRTC SDP Offer from client")
    try:
        # 1. Establish WebRTC Connection
        connection = SmallWebRTCConnection()
        
        # 2. Process SDP Offer and generate SDP Answer
        await connection.initialize(offer.sdp, offer.type)
        answer = connection.get_answer()
        
        if not answer:
            raise HTTPException(status_code=500, detail="Failed to generate WebRTC SDP Answer")
            
        logger.info("Successfully generated WebRTC SDP Answer. Spawning pipeline...")
        
        # 3. Setup transport
        transport_params = TransportParams(
            audio_out_enabled=True,
            audio_in_enabled=True,
        )
        transport = SmallWebRTCTransport(
            webrtc_connection=connection,
            params=transport_params
        )
        
        # 4. Spawn the Pipecat pipeline in a background task
        # We run it as an asyncio task so that it runs concurrently with FastAPI
        asyncio.create_task(run_voice_pipeline(transport, connection))
        
        return answer
        
    except Exception as e:
        logger.error(f"Error establishing WebRTC call session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/answer")
async def answer_call(request: Request):
    """
    Plivo Answer XML Endpoint.
    Returns Plivo XML with a <Stream> element pointing to our WSS/WS endpoint.
    Supports dynamic Host header resolution for local ngrok tunnels.
    """
    logger.info("Received Plivo Answer URL request")
    
    # 1. Resolve host and scheme dynamically, or use config fallback
    host = request.headers.get("host")
    scheme = "wss" if request.url.scheme == "https" else "ws"
    
    # Check if PUBLIC_BASE_URL overrides this (but fallback if it's default localhost)
    public_url = os.getenv("PUBLIC_BASE_URL", "")
    if public_url and "localhost" not in public_url:
        ws_url = public_url.replace("http://", "ws://").replace("https://", "wss://").rstrip("/") + "/ws"
    else:
        ws_url = f"{scheme}://{host}/ws"
        
    logger.info(f"Returning Plivo stream Answer XML pointing to: {ws_url}")
    
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Stream bidirectional="true" keepCallAlive="true" contentType="audio/x-mulaw;rate=8000">
    {ws_url}
  </Stream>
</Response>"""

    return Response(content=xml_content, media_type="application/xml")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Plivo WebSocket Endpoint.
    Receives Plivo media events, decodes them using PlivoFrameSerializer,
    and runs the Pipecat pipeline using FastAPIWebsocketTransport.
    """
    await websocket.accept()
    logger.info("Plivo WebSocket connection accepted. Waiting for 'start' event...")
    
    try:
        # 1. Receive the first message from Plivo to extract streamId and callId
        message_str = await websocket.receive_text()
        message = json.loads(message_str)
        
        if message.get("event") != "start":
            logger.error(f"Expected 'start' event but got: {message.get('event')}")
            await websocket.close()
            return
            
        start_data = message.get("start", {})
        stream_id = start_data.get("streamId")
        call_id = start_data.get("callId")
        
        if not stream_id or not call_id:
            logger.error(f"Missing streamId ({stream_id}) or callId ({call_id}) in 'start' event")
            await websocket.close()
            return
            
        logger.info(f"Plivo Stream started. StreamID: {stream_id}, CallID: {call_id}")
        
        # 2. Instantiate the Plivo serializer.
        # Credentials are required only if auto_hang_up is enabled.
        auth_id = os.getenv("PLIVO_AUTH_ID")
        auth_token = os.getenv("PLIVO_AUTH_TOKEN")
        
        auto_hang_up = bool(auth_id and auth_token)
        if not auto_hang_up:
            logger.warning("PLIVO_AUTH_ID and/or PLIVO_AUTH_TOKEN not configured. Disabling auto_hang_up.")
            
        serializer = PlivoFrameSerializer(
            stream_id=stream_id,
            call_id=call_id,
            auth_id=auth_id,
            auth_token=auth_token,
            params=PlivoFrameSerializer.InputParams(
                plivo_sample_rate=8000,
                auto_hang_up=auto_hang_up,
            )
        )
        
        # 3. Instantiate the FastAPI WebSockets transport
        transport = FastAPIWebsocketTransport(
            websocket=websocket,
            params=FastAPIWebsocketParams(
                audio_out_enabled=True,
                audio_in_enabled=True,
                add_wav_header=False,
                serializer=serializer,
            )
        )
        
        logger.info("FastAPIWebsocketTransport initialized. Launching voice pipeline...")
        
        # 4. Run the voice pipeline
        # We run it synchronously within the websocket handler to keep the socket alive
        # until the pipeline finishes executing or client disconnects.
        await run_voice_pipeline(transport)
        
    except Exception as e:
        logger.error(f"Error handling Plivo WebSocket: {e}", exc_info=True)
        # Attempt to close socket if still open
        try:
            await websocket.close()
        except Exception:
            pass
    finally:
        logger.info("Plivo WebSocket session closed.")

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("WS_HOST", "0.0.0.0")
    port = int(os.getenv("WS_PORT", 8765))
    logger.info(f"Starting FastAPI server on {host}:{port}...")
    uvicorn.run(app, host=host, port=port)
