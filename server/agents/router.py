import os
import logging
from typing import Any
from pipecat.services.llm_service import LLMService
from pipecat_subagents.agents.llm import LLMContextAgent, tool
from server.pipeline.llm_adapter import get_llm_service

logger = logging.getLogger("pipecat")

class RouterAgent(LLMContextAgent):
    """
    Router Agent responsible for greeting the user, identifying their intent,
    and classifying the conversation to route it to specialized subagents.
    Uses fast and multilingual Google Gemini by default.
    """
    
    def __init__(self, name: str, *, bus: Any, active: bool = False):
        super().__init__(name, bus=bus, active=active)
        logger.info("RouterAgent initialized.")

    def build_llm(self) -> LLMService:
        """
        Builds the LLM service for the Router. Uses Gemini by default
        for fast classification and strong multilingual support.
        """
        system_instruction = (
            "You are the ROUTER agent for Preet Voicebot Platform.\n"
            "Your ONLY tasks are:\n"
            "1. Greet the user briefly if they just connected.\n"
            "2. Identify what the user needs. They can need general conversation/smalltalk, "
            "or specific customer support (technical assistance, account help, password reset).\n"
            "3. If they ask a support-related question, call the tool 'handoff_to_support' immediately. "
            "Do NOT try to answer support questions yourself!\n"
            "4. Keep your responses extremely brief (1-2 sentences at most).\n"
            "5. Always respond in the caller's detected language."
        )
        provider = os.getenv("ROUTER_LLM", "gemini")
        return get_llm_service(
            provider=provider,
            system_instruction=system_instruction
        )

    @tool
    async def handoff_to_support(self) -> str:
        """
        Classification tool to hand off control to the Support Specialist.
        Call this immediately when the user requests general support, account assistance, 
        password help, technical issues, or refund requests.
        """
        logger.info("Router calling handoff_to_support tool...")
        # Summarize context before handoff (or let standard handoff happen)
        await self.handoff_to("support")
        return "Handoff successfully initiated."
