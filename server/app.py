import os
import logging
import asyncio
from dotenv import load_dotenv

# Load env variables before other imports
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
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

class WebRTCOffer(BaseModel):
    sdp: str
    type: str

@app.get("/health")
def health_check():
    """
    Simple liveness and readiness probe.
    """
    return {
        "status": "healthy",
        "pipecat_version": "1.3.0",
        "router_llm": os.getenv("ROUTER_LLM", "gemini")
    }

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
        # You can specify custom ice_servers here if needed, e.g. stun/turn
        connection = SmallWebRTCConnection()
        
        # 2. Process SDP Offer and generate SDP Answer
        await connection.initialize(offer.sdp, offer.type)
        answer = connection.get_answer()
        
        if not answer:
            raise HTTPException(status_code=500, detail="Failed to generate WebRTC SDP Answer")
            
        logger.info("Successfully generated WebRTC SDP Answer. Spawning pipeline...")
        
        # 3. Spawn the Pipecat pipeline in a background task
        # We run it as an asyncio task so that it runs concurrently with FastAPI
        asyncio.create_task(run_voice_pipeline(connection))
        
        return answer
        
    except Exception as e:
        logger.error(f"Error establishing WebRTC call session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("WS_HOST", "0.0.0.0")
    port = int(os.getenv("WS_PORT", 8765))
    logger.info(f"Starting FastAPI server on {host}:{port}...")
    uvicorn.run(app, host=host, port=port)
