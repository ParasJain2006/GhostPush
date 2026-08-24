import os
from typing import Any, Optional


class MockLLM:
    """Fallback LLM used when no valid external API key is supplied in runtime configuration."""

    def __init__(self, provider: str = "mock"):
        self.provider = provider

    def invoke(self, prompt: Any) -> Any:
        content_str = str(prompt)
        class MockMessage:
            def __init__(self, content: str):
                self.content = content
        
        # Generate a structured fallback README text
        readme_text = f"""# Code Solution Documentation

## Overview
Automated code solution documentation generated via {self.provider.upper()}.

## Solution Details
The submitted solution addresses the problem statement using optimal data structures and logic.

## Complexity Analysis
- **Time Complexity:** O(N)
- **Space Complexity:** O(1)
"""
        return MockMessage(readme_text)


def get_llm_provider(
    provider_name: Optional[str] = None,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: float = 0.2,
) -> Any:
    """Factory function that returns a LangChain Chat Model based on Tray App runtime configuration.

    Prioritizes provider_name, model_name, and api_key supplied by the client (e.g. Tray App runtime payload).
    If missing or invalid/dummy, falls back to MockLLM.
    """
    if not provider_name or not provider_name.strip():
        provider_name = "gemini"

    provider_name = provider_name.lower().strip()

    def is_dummy_key(key: Optional[str]) -> bool:
        if not key:
            return True
        key_lower = key.lower().strip()
        return "dummy" in key_lower or "your_" in key_lower or key_lower == "change_me"

    resolved_key = (api_key and api_key.strip()) or ""

    if provider_name == "gemini":
        if is_dummy_key(resolved_key):
            return MockLLM(provider="gemini (Mock Mode - Missing or Invalid API Key)")
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            model = model_name or "gemini-1.5-flash"
            return ChatGoogleGenerativeAI(
                model=model,
                google_api_key=resolved_key,
                temperature=temperature,
            )
        except ImportError:
            return MockLLM(provider="gemini (langchain_google_genai missing)")

    elif provider_name == "openai":
        if is_dummy_key(resolved_key):
            return MockLLM(provider="openai (Mock Mode - Missing or Invalid API Key)")
        try:
            from langchain_openai import ChatOpenAI
            model = model_name or "gpt-4o-mini"
            return ChatOpenAI(
                model=model,
                api_key=resolved_key,
                temperature=temperature,
            )
        except ImportError:
            return MockLLM(provider="openai (langchain_openai missing)")

    elif provider_name == "anthropic":
        if is_dummy_key(resolved_key):
            return MockLLM(provider="anthropic (Mock Mode - Missing or Invalid API Key)")
        try:
            from langchain_community.chat_models import ChatAnthropic
            return ChatAnthropic(
                model=model_name or "claude-3-haiku-20240307",
                anthropic_api_key=resolved_key,
                temperature=temperature,
            )
        except Exception:
            return MockLLM(provider="anthropic")

    elif provider_name == "groq":
        if is_dummy_key(resolved_key):
            return MockLLM(provider="groq (Mock Mode - Missing or Invalid API Key)")
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=model_name or "llama3-8b-8192",
                openai_api_key=resolved_key,
                openai_api_base="https://api.groq.com/openai/v1",
                temperature=temperature,
            )
        except Exception:
            return MockLLM(provider="groq")

    # Default fallback
    return MockLLM(provider=provider_name)


