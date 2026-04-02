"""
OpenLoopholes.com — AI Provider Abstraction

Supports multiple AI providers via environment variables:

  AI_PROVIDER=openrouter   (default) — OpenRouter API, any model
  AI_PROVIDER=anthropic    — Anthropic API (Claude models)
  AI_PROVIDER=openclaw     — OpenClaw local gateway (uses your configured model)

Models are configurable:
  LOOP_MODEL       — model for iteration loop (default: google/gemini-3.1-flash-lite-preview)
  VALIDATION_MODEL — model for final validation (default: google/gemini-3-flash-preview)
  DISCOVERY_MODEL  — model for strategy discovery (default: same as VALIDATION_MODEL)

For OpenClaw: models default to "openclaw/default" (routes to whatever you configured).
Override with LOOP_MODEL/VALIDATION_MODEL if you want a specific model.

Auto-detection: if AI_PROVIDER is not set, checks for available API keys/services.

Logs are written to logs/ directory (one file per session).
"""

from __future__ import annotations

import datetime
import logging
import os
import sys
import time
from pathlib import Path

import openai


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
RUN_TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def setup_logging() -> logging.Logger:
    """Set up file + console logging. Logs go to logs/ directory."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = RUN_TIMESTAMP
    log_file = LOG_DIR / f"openloopholes_{timestamp}.log"

    logger = logging.getLogger("openloopholes")
    if logger.handlers:
        return logger  # already set up

    logger.setLevel(logging.DEBUG)

    # File handler — full detail with timestamps
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    ))
    logger.addHandler(fh)

    # Console handler — bare output (looks identical to print())
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(ch)

    logger.debug(f"Log file: {log_file}")
    return logger


log = setup_logging()


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_LOOP_MODEL = "google/gemini-3.1-flash-lite-preview"
DEFAULT_VALIDATION_MODEL = "google/gemini-3-flash-preview"
OPENCLAW_DEFAULT_MODEL = "openclaw/default"

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
        "key_env": "OPENCLAW_API_KEY",
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
        log.debug(f"Provider explicitly set: {explicit}")
        return explicit

    # Check for API keys in order of preference
    if os.environ.get("OPENROUTER_API_KEY"):
        log.debug("Auto-detected provider: openrouter")
        return "openrouter"
    if os.environ.get("ANTHROPIC_API_KEY"):
        log.debug("Auto-detected provider: anthropic")
        return "anthropic"

    # Check if OpenClaw gateway is running (requires bearer token for all endpoints)
    openclaw_key = os.environ.get("OPENCLAW_API_KEY", "")
    if openclaw_key:
        try:
            import urllib.request
            req = urllib.request.Request(
                "http://127.0.0.1:18789/v1/models",
                headers={"Authorization": f"Bearer {openclaw_key}"},
            )
            urllib.request.urlopen(req, timeout=2)
            log.debug("Auto-detected provider: openclaw (gateway responding with auth)")
            return "openclaw"
        except Exception:
            pass
    else:
        # No key set — try without auth in case gateway has auth disabled
        try:
            import urllib.request
            urllib.request.urlopen("http://127.0.0.1:18789/v1/models", timeout=2)
            log.debug("Auto-detected provider: openclaw (gateway responding, no auth)")
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

    if provider == "openclaw":
        api_key = os.environ.get("OPENCLAW_API_KEY", "openclaw")
    else:
        api_key = os.environ.get(config["key_env"], "")
        if not api_key:
            print(f"ERROR: {config['key_env']} environment variable not set")
            sys.exit(1)

    return provider, base_url, api_key


# ---------------------------------------------------------------------------
# Model resolution
# ---------------------------------------------------------------------------
def get_loop_model() -> str:
    explicit = os.environ.get("LOOP_MODEL")
    if explicit:
        return explicit
    if detect_provider() == "openclaw":
        return OPENCLAW_DEFAULT_MODEL
    return DEFAULT_LOOP_MODEL


def get_validation_model() -> str:
    explicit = os.environ.get("VALIDATION_MODEL")
    if explicit:
        return explicit
    if detect_provider() == "openclaw":
        return OPENCLAW_DEFAULT_MODEL
    return DEFAULT_VALIDATION_MODEL


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
    log.debug(f"Client initialized: provider={provider}, base_url={base_url}")
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

    # response_format not supported by OpenClaw
    if json_mode and _provider_name != "openclaw":
        kwargs["response_format"] = {"type": "json_object"}

    log.debug(f"LLM call: model={model_id}, provider={_provider_name}, "
              f"system_len={len(system_prompt)}, user_len={len(user_prompt)}")

    for attempt in range(MAX_RETRIES):
        try:
            start = time.time()
            response = client.chat.completions.create(**kwargs)
            elapsed = time.time() - start
            content = response.choices[0].message.content
            log.debug(f"LLM response: {elapsed:.1f}s, {len(content)} chars")
            return content
        except Exception as e:
            log.warning(f"LLM error (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF[attempt]
                print(f"  API error (attempt {attempt + 1}): {e}. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                log.error(f"LLM call failed after {MAX_RETRIES} attempts: {e}")
                raise

    raise RuntimeError("Exhausted retries")
