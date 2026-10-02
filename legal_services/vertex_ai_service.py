"""Gemini en Vertex AI (Cloud Run usa credenciales del servicio automáticamente)."""
from __future__ import annotations

import os

_client = None


def is_configured() -> bool:
    return bool((os.environ.get("GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT") or "").strip())


def _project() -> str:
    return (
        (os.environ.get("GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT") or "").strip()
    )


def _location() -> str:
    return (os.environ.get("GCP_REGION") or os.environ.get("VERTEX_LOCATION") or "us-central1").strip()


def model_id() -> str:
    return (os.environ.get("VERTEX_MODEL") or "gemini-2.5-flash").strip()


def _get_client():
    global _client
    if _client is None:
        from google import genai

        _client = genai.Client(vertexai=True, project=_project(), location=_location())
    return _client


def _track_usage(tenant_id: str | None, response) -> None:
    meta = getattr(response, "usage_metadata", None)
    if not tenant_id or not meta:
        return
    from legal_services.usage_service import record_token_usage

    prompt = int(getattr(meta, "prompt_token_count", 0) or 0)
    completion = int(getattr(meta, "candidates_token_count", 0) or 0)
    total = int(getattr(meta, "total_token_count", 0) or 0) or (prompt + completion)
    if total > 0:
        record_token_usage(tenant_id, total=total, prompt=prompt, completion=completion)


def chat_completion(
    system_prompt: str, user_content: str, max_tokens: int = 3500, tenant_id: str | None = None
) -> str:
    if not is_configured():
        raise RuntimeError("Vertex no configurado (GCP_PROJECT).")
    from google.genai import types

    client = _get_client()
    response = client.models.generate_content(
        model=model_id(),
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=max_tokens,
            temperature=0.2,
        ),
    )
    _track_usage(tenant_id, response)
    return (response.text or "").strip()


def chat_completion_messages(
    messages: list[dict], max_tokens: int = 3500, tenant_id: str | None = None
) -> str:
    if not is_configured():
        raise RuntimeError("Vertex no configurado (GCP_PROJECT).")
    from google.genai import types

    system_parts: list[str] = []
    contents: list[types.Content] = []
    for msg in messages:
        role = (msg.get("role") or "user").lower()
        text = (msg.get("content") or "").strip()
        if not text:
            continue
        if role == "system":
            system_parts.append(text)
            continue
        vertex_role = "model" if role in ("assistant", "model") else "user"
        contents.append(types.Content(role=vertex_role, parts=[types.Part.from_text(text)]))

    if not contents:
        raise ValueError("Sin mensajes para el modelo.")

    client = _get_client()
    config = types.GenerateContentConfig(
        max_output_tokens=max_tokens,
        temperature=0.25,
    )
    if system_parts:
        config = types.GenerateContentConfig(
            system_instruction="\n\n".join(system_parts),
            max_output_tokens=max_tokens,
            temperature=0.25,
        )

    response = client.models.generate_content(
        model=model_id(),
        contents=contents,
        config=config,
    )
    _track_usage(tenant_id, response)
    return (response.text or "").strip()
