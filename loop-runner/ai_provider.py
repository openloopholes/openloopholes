"""
OpenLoopholes.com — AI Provider Abstraction

Supports multiple AI providers via environment variables:

  AI_PROVIDER=openrouter   (default) — OpenRouter API, any model
  AI_PROVIDER=anthropic    — Anthropic API (Claude models)
  AI_PROVIDER=openclaw     — OpenClaw local gateway

Models are configurable:
  LOOP_MODEL       — model for iteration loop (default: google/gemini-3.1-flash-lite-preview)
  VALIDATION_MODEL — model for final validation (default: google/gemini-3-flash-preview)
  DISCOVERY_MODEL  — model for strategy discovery (default: same as VALIDATION_MODEL)

Auto-detection: if AI_PROVIDER is not set, checks for available API keys/services.
"""

from __future__ import annotations

import os
import sys
import time

import openai


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_LOOP_MODEL = "google/gemini-3.1-flash-lite-preview"
DEFAULT_VALIDATION_MODEL = "google/gemini-3-flash-preview"

PROVIDER_CONFIGS = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "key_env": "OPENROUTER_API_KEY",
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1",
        "key_env": "ANTHROPIC_API_KEY",
    },
    "openclaw": {
        "base_url": "http://127.0.0.1:18789/v1",
        "key_env": None,  # OpenClaw uses its own auth
    },
}

MAX_RETRIES = 3
RETRY_BACKOFF = [1, 4, 16]


# ---------------------------------------------------------------------------
# Provider detection
# ---------------------------------------------------------------------------
def detect_provider() -> str:
    """Auto-detect which AI provider is available."""
    explicit = os.environ.get("AI_PROVIDER", "").lower()
    if explicit and explicit in PROVIDER_CONFIGS:
        return explicit

    # Check for API keys in order of preference
    if os.environ.get("OPENROUTER_API_KEY"):
        return "openrouter"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"

    # Check if OpenClaw gateway is running
    try:
        import urllib.request
        urllib.request.urlopen("http://127.0.0.1:18789/health", timeout=2)
        return "openclaw"
    except Exception:
        pass

    return ""


def get_provider_info() -> tuple[str, str, str]:
    """Returns (provider_name, base_url, api_key)."""
    provider = detect_provider()
    if not provider:
        print("ERROR: No AI provider configured.")
        print()
        print("Set one of the following:")
        print("  export OPENROUTER_API_KEY=your_key    # OpenRouter (recommended)")
        print("  export ANTHROPIC_API_KEY=your_key     # Anthropic (Claude models)")
        print("  # Or start OpenClaw gateway            # OpenClaw (local)")
        print()
        print("Optionally set AI_PROVIDER=openrouter|anthropic|openclaw")
        print("Optionally set LOOP_MODEL, VALIDATION_MODEL, DISCOVERY_MODEL")
        sys.exit(1)

    config = PROVIDER_CONFIGS[provider]
    base_url = config["base_url"]

    if config["key_env"]:
        api_key = os.environ.get(config["key_env"], "")
        if not api_key:
            print(f"ERROR: {config['key_env']} environment variable not set")
            sys.exit(1)
    else:
        api_key = "openclaw"  # OpenClaw doesn't need a real key

    return provider, base_url, api_key


# ---------------------------------------------------------------------------
# Model resolution
# ---------------------------------------------------------------------------
def get_loop_model() -> str:
    return os.environ.get("LOOP_MODEL", DEFAULT_LOOP_MODEL)


def get_validation_model() -> str:
    return os.environ.get("VALIDATION_MODEL", DEFAULT_VALIDATION_MODEL)


def get_discovery_model() -> str:
    return os.environ.get("DISCOVERY_MODEL", get_validation_model())


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------
_client = None
_provider_name = None


def get_client() -> openai.OpenAI:
    """Get or create the OpenAI-compatible client for the configured provider."""
    global _client, _provider_name
    if _client is not None:
        return _client

    provider, base_url, api_key = get_provider_info()
    _provider_name = provider
    _client = openai.OpenAI(base_url=base_url, api_key=api_key)
    return _client


def get_provider_name() -> str:
    """Get the name of the active provider."""
    global _provider_name
    if _provider_name is None:
        get_client()
    return _provider_name


# ---------------------------------------------------------------------------
# LLM call with retries
# ---------------------------------------------------------------------------
def call_llm(model_id: str, system_prompt: str, user_prompt: str,
             temperature: float = 0.7, json_mode: bool = True) -> str:
    """
    Call LLM via the configured provider with retries and exponential backoff.
    Returns raw response text.
    """
    client = get_client()

    kwargs = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
    }

    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(**kwargs)
            return response.choices[0].message.content
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF[attempt]
                print(f"  API error (attempt {attempt + 1}): {e}. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise

    raise RuntimeError("Exhausted retries")
