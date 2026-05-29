import os
from typing import Any
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.google.llm import GoogleLLMService

def get_llm_service(
    provider: str | None = None,
    model: str | None = None,
    system_instruction: str | None = None,
    **kwargs: Any
) -> Any:
    """
    Factory function to get the appropriate LLM Service based on the configured provider.
    This abstracts OpenAI and Google Gemini so they can be seamlessly swapped.
    """
    # Fallback to env-defined default if provider is not passed
    if not provider:
        provider = os.getenv("ROUTER_LLM", "gemini").lower()
    else:
        provider = provider.lower()

    if provider == "openai":
        # Default model for OpenAI in voice is gpt-4o-mini
        llm_model = model or "gpt-4o-mini"
        
        # OpenAI LLM Service parameters
        # OpenAI in Pipecat 1.3.0 supports system instruction via constructor kwargs or settings/messages.
        # But we can also set the prompt in the system instruction if supported or feed it in.
        # In Pipecat, system instructions can be set via system_instruction or system_prompt.
        # OpenAILLMService supports system_instruction/system_prompt in constructor or settings.
        # Let's pass standard constructor arguments.
        service_args = {
            "model": llm_model,
        }
        # If we have custom kwargs, add them
        service_args.update(kwargs)
        
        service = OpenAILLMService(**service_args)
        
        # If system instruction is provided, we can set it
        if system_instruction:
            # OpenAILLMService has a set_system_instruction method or standard prompt injection
            if hasattr(service, "set_system_instruction"):
                service.set_system_instruction(system_instruction)
            
        return service

    elif provider == "gemini" or provider == "google":
        # Default model for Gemini in voice is gemini-1.5-flash
        llm_model = model or "gemini-1.5-flash"
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is not set")
            
        service_args = {
            "api_key": api_key,
            "model": llm_model,
        }
        if system_instruction:
            service_args["system_instruction"] = system_instruction
            
        service_args.update(kwargs)
        return GoogleLLMService(**service_args)

    else:
        raise ValueError(f"Unknown LLM provider: {provider}. Supported: 'openai', 'gemini'")
