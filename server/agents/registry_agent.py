import os
import logging
from typing import Any
from pipecat.services.llm_service import LLMService
from pipecat_subagents.agents.llm import LLMContextAgent
from server.pipeline.llm_adapter import get_llm_service

logger = logging.getLogger("pipecat")

class RegistryAgent(LLMContextAgent):
    """
    RegistryAgent is a dynamic subagent that loads its prompt, provider, and tools
    configuration directly from the JSON agent registry, dynamically registering handoff tools.
    """
    def __init__(self, name: str, *, prompt: str, provider: str, tools_config: list, bus: Any, active: bool = False):
        super().__init__(name, bus=bus, active=active)
        self._prompt = prompt
        self._provider = provider
        self._tools_config = tools_config
        logger.info(f"RegistryAgent '{name}' initialized with provider '{provider}'.")

    def build_llm(self) -> LLMService:
        """
        Builds the LLM service dynamically configured with the prompt and provider.
        """
        return get_llm_service(
            provider=self._provider,
            system_instruction=self._prompt
        )

    def build_tools(self) -> list:
        """
        Dynamically builds the list of handoff functions based on the tools config.
        """
        tools = []
        for t in self._tools_config:
            name = t.get("name")
            description = t.get("description")
            target = t.get("target_agent")
            
            if name and target:
                def make_tool(t_name=name, t_desc=description, t_target=target):
                    async def handoff_fn() -> str:
                        logger.info(f"Agent '{self.name}' executing dynamic tool '{t_name}' -> routing to '{t_target}'")
                        await self.handoff_to(t_target)
                        return f"Successfully initiated handoff to '{t_target}'."
                    
                    handoff_fn.__name__ = t_name
                    handoff_fn.__doc__ = t_desc
                    return handoff_fn
                
                tools.append(make_tool())
        return tools
