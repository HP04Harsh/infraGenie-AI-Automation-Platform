"""Pluggable AI orchestration provider for InfraGenie.

Supports:
  - azure_openai  (api-key based, fast path)
  - foundry       (Azure AI Foundry Agent Service via Entra ID Service Principal)

The provider for each user is loaded from db.ai_configs (set in onboarding / Settings).
If no config exists, falls back to env vars AZURE_OPENAI_* — used to seed the demo.
"""
from __future__ import annotations

import os
import re
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ai_provider")

# Env-fallback creds for the demo (also seeded into db.ai_configs for the guest user)
FALLBACK_AZURE_OPENAI = {
    "provider": "azure_openai",
    "endpoint": os.environ.get(
        "AZURE_OPENAI_ENDPOINT",
        "https://infragenie.openai.azure.com/openai/v1",
    ),
    "api_key": os.environ.get(
        "AZURE_OPENAI_API_KEY",
        "",
    ),
    "deployment": os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-5"),
}


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def parse_json_response(text: str) -> Dict[str, Any]:
    """Best-effort parse — strip code fences, find first { ... } JSON object."""
    if not text:
        return {}
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    # Find first JSON object
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception as e:
        logger.warning("JSON parse failed: %s — raw=%s", e, text[:200])
        return {}


async def load_user_config(db, user: dict) -> Dict[str, Any]:
    """Load the user's AI config from MongoDB; fall back to envs."""
    if not user:
        return FALLBACK_AZURE_OPENAI
    doc = await db.ai_configs.find_one({"user_id": user["id"]}, {"_id": 0, "user_id": 0})
    if doc and doc.get("provider"):
        return doc
    return FALLBACK_AZURE_OPENAI


# ----------------------------------------------------------------------
# Provider: Azure OpenAI (api-key based)
# ----------------------------------------------------------------------
_aoai_clients: Dict[str, Any] = {}  # endpoint+key -> AsyncOpenAI


def _get_aoai_client(cfg: Dict[str, Any]):
    from openai import AsyncOpenAI

    endpoint = (cfg.get("endpoint") or "").rstrip("/")
    key = cfg.get("api_key") or ""
    cache_key = f"{endpoint}|{key[:8]}"
    if cache_key in _aoai_clients:
        return _aoai_clients[cache_key]
    client = AsyncOpenAI(base_url=endpoint, api_key=key)
    _aoai_clients[cache_key] = client
    return client


async def _chat_azure_openai(
    cfg: Dict[str, Any],
    system: str,
    user_text: str,
    response_json: bool = True,
) -> str:
    client = _get_aoai_client(cfg)
    deployment = cfg.get("deployment") or "gpt-4o"
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_text},
    ]
    try:
        kwargs = {"model": deployment, "messages": messages}
        if response_json:
            kwargs["response_format"] = {"type": "json_object"}
        resp = await client.chat.completions.create(**kwargs)
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        # Some deployments / models don't support response_format=json_object — retry without it
        if response_json:
            logger.warning("AOAI json_object unsupported, retrying without: %s", e)
            try:
                resp = await client.chat.completions.create(model=deployment, messages=messages)
                return (resp.choices[0].message.content or "").strip()
            except Exception as e2:
                raise e2
        raise


# ----------------------------------------------------------------------
# Provider: Azure AI Foundry Agent Service (Entra ID via Service Principal)
# ----------------------------------------------------------------------
_foundry_clients: Dict[str, Any] = {}


def _get_foundry_client(cfg: Dict[str, Any]):
    """Build AIProjectClient using ClientSecretCredential from the user's onboarding SP."""
    from azure.identity.aio import ClientSecretCredential
    from azure.ai.projects.aio import AIProjectClient

    project_endpoint = cfg.get("endpoint") or cfg.get("project_endpoint")
    tenant_id = cfg.get("tenant_id")
    client_id = cfg.get("client_id")
    client_secret = cfg.get("client_secret")
    cache_key = f"{project_endpoint}|{client_id}"
    if cache_key in _foundry_clients:
        return _foundry_clients[cache_key]

    if not all([project_endpoint, tenant_id, client_id, client_secret]):
        raise ValueError("Foundry config missing endpoint / tenant_id / client_id / client_secret")

    credential = ClientSecretCredential(
        tenant_id=tenant_id, client_id=client_id, client_secret=client_secret
    )
    client = AIProjectClient(endpoint=project_endpoint, credential=credential)
    _foundry_clients[cache_key] = client
    return client


async def _chat_foundry(
    cfg: Dict[str, Any],
    system: str,
    user_text: str,
    response_json: bool = True,
) -> str:
    """One-shot foundry agent call (creates ephemeral agent + thread for simplicity).

    For production-grade multi-turn we'd persist the thread_id per session. Phase 1 is
    happy with one-shot calls because our orchestrator carries its own session state.
    """
    project_client = _get_foundry_client(cfg)
    deployment = cfg.get("deployment") or "gpt-4o"
    agent_name = cfg.get("agent_name") or "InfraGenieOrchestrator"

    async with project_client:
        agents = project_client.agents
        # Re-use an agent with our name if it exists; else create one.
        agent_id = None
        try:
            async for a in agents.list_agents():
                if a.name == agent_name:
                    agent_id = a.id
                    break
        except Exception as e:
            logger.warning("Foundry list_agents failed: %s", e)

        if agent_id is None:
            new_agent = await agents.create_agent(
                model=deployment, name=agent_name, instructions=system
            )
            agent_id = new_agent.id

        thread = await agents.threads.create()
        await agents.messages.create(thread_id=thread.id, role="user", content=user_text)

        kwargs = {"thread_id": thread.id, "agent_id": agent_id}
        if response_json:
            kwargs["response_format"] = {"type": "json_object"}
        run = await agents.runs.create_and_process(**kwargs)
        if run.status == "failed":
            raise RuntimeError(f"Foundry run failed: {run.last_error}")

        # Pull latest assistant message
        last_text = ""
        async for m in agents.messages.list(thread_id=thread.id):
            if m.role == "assistant":
                for part in (m.content or []):
                    if hasattr(part, "text") and part.text is not None:
                        last_text = (part.text.value if hasattr(part.text, "value") else str(part.text)) + last_text
                break
        return last_text


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# Provider: Emergent (OpenAI-compatible via emergentintegrations)
# ----------------------------------------------------------------------
_emergent_clients: Dict[str, Any] = {}


def _get_emergent_client(cfg: Dict[str, Any]):
    from openai import AsyncOpenAI

    key = cfg.get("api_key") or ""
    cache_key = f"emergent|{key[:8]}"
    if cache_key in _emergent_clients:
        return _emergent_clients[cache_key]
    client = AsyncOpenAI(
        api_key=key,
        base_url="https://integrations.emergentagent.com/llm/openai/v1",
    )
    _emergent_clients[cache_key] = client
    return client


async def _chat_emergent(
    cfg: Dict[str, Any],
    system: str,
    user_text: str,
    response_json: bool = True,
) -> str:
    client = _get_emergent_client(cfg)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_text},
    ]
    try:
        kwargs = {"model": "gpt-4o", "messages": messages}
        if response_json:
            kwargs["response_format"] = {"type": "json_object"}
        resp = await client.chat.completions.create(**kwargs)
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        if response_json:
            logger.warning("Emergent json_object unsupported, retrying without: %s", e)
            try:
                resp = await client.chat.completions.create(model="gpt-4o", messages=messages)
                return (resp.choices[0].message.content or "").strip()
            except Exception as e2:
                raise e2
        raise


async def chat_completion(
    cfg: Dict[str, Any],
    system: str,
    user_text: str,
    response_json: bool = True,
) -> str:
    """Run a single chat completion through the configured provider."""
    provider = (cfg or {}).get("provider", "azure_openai")
    if provider == "foundry":
        return await _chat_foundry(cfg, system, user_text, response_json=response_json)
    if provider == "emergent":
        return await _chat_emergent(cfg, system, user_text, response_json=response_json)
    return await _chat_azure_openai(cfg, system, user_text, response_json=response_json)


async def chat_json(
    cfg: Dict[str, Any],
    system: str,
    user_text: str,
) -> Dict[str, Any]:
    """Chat → parsed JSON. Returns {} if parsing fails."""
    raw = await chat_completion(cfg, system, user_text, response_json=True)
    return parse_json_response(raw)
