import os
import logging
from typing import Any
from pipecat.services.llm_service import LLMService
from pipecat_subagents.agents.llm import LLMContextAgent, tool
from server.pipeline.llm_adapter import get_llm_service

logger = logging.getLogger("pipecat")

class SupportAgent(LLMContextAgent):
    """
    Support Specialist Agent responsible for answering technical support queries,
    account troubleshooting, and customer help.
    Uses OpenAI by default for strong, structured reasoning.
    """
    
    def __init__(self, name: str, *, bus: Any, active: bool = False):
        super().__init__(name, bus=bus, active=active)
        logger.info("SupportAgent initialized.")

    def build_llm(self) -> LLMService:
        """
        Builds the LLM service for the Support Agent. Uses OpenAI by default
        for nuanced technical reasoning and troubleshooting.
        """
        system_instruction = (
            "You are the SUPPORT SPECIALIST for Preet Voicebot Platform.\n"
            "Your ONLY task is to help the user with customer support issues, technical assistance, "
            "and account troubleshooting.\n"
            "Keep your responses extremely helpful, professional, and very brief (1-2 sentences at most).\n"
            "Do NOT read out bullet points, lists, or markdown as you are speaking out loud.\n"
            "If the user asks about billing, sales, or general topics unrelated to technical support, "
            "or if the user says they are done, call the 'return_to_router' tool immediately to route them back.\n"
            "Always respond in the caller's detected language."
        )
        provider = os.getenv("SPECIALIST_LLM", "openai")
        return get_llm_service(
            provider=provider,
            system_instruction=system_instruction
        )

    @tool
    async def return_to_router(self) -> str:
        """
        Tool to return the conversation control back to the central Router.
        Call this immediately when the user is done with support, or asks about sales, 
        billing, or other non-support topics.
        """
        logger.info("Support agent calling return_to_router tool...")
        await self.handoff_to("router")
        return "Control successfully returned to the Router."
