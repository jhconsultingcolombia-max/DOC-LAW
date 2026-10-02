"""Gemini en Vertex AI (Cloud Run: credenciales del servicio)."""
from __future__ import annotations

import os

_inited = False


def is_configured() -> bool:
    return bool((os.environ.get("GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT") or "").strip())


def _project() -> str:
    return (os.environ.get("GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT") or "").strip()


def _location() -> str:
    return (os.environ.get("GCP_REGION") or os.environ.get("VERTEX_LOCATION") or "us-central1").strip()


def model_id() -> str:
    return (os.environ.get("VERTEX_MODEL") or "gemini-2.5-flash").strip()


def _ensure_init() -> None:
    global _inited
    if _inited:
        return
    import vertexai

    vertexai.init(project=_project(), location=_location())
    _inited = True


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
    from vertexai.generative_models import GenerationConfig, GenerativeModel

    _ensure_init()
    model = GenerativeModel(model_id(), system_instruction=[system_prompt])
    response = model.generate_content(
        user_content,
        generation_config=GenerationConfig(max_output_tokens=max_tokens, temperature=0.2),
    )
    _track_usage(tenant_id, response)
    return (response.text or "").strip()


def chat_completion_messages(
    messages: list[dict], max_tokens: int = 3500, tenant_id: str | None = None
) -> str:
    if not is_configured():
        raise RuntimeError("Vertex no configurado (GCP_PROJECT).")
    from vertexai.generative_models import Content, GenerationConfig, GenerativeModel, Part

    _ensure_init()
    system_parts: list[str] = []
    history: list[Content] = []
    last_user = ""

    for msg in messages:
        role = (msg.get("role") or "user").lower()
        text = (msg.get("content") or "").strip()
        if not text:
            continue
        if role == "system":
            system_parts.append(text)
            continue
        if role == "user":
            last_user = text
            history.append(Content(role="user", parts=[Part.from_text(text)]))
        else:
            history.append(Content(role="model", parts=[Part.from_text(text)]))

    if not last_user:
        raise ValueError("Sin mensaje de usuario.")

    prior = history[:-1] if len(history) > 1 else []
    model = GenerativeModel(
        model_id(),
        system_instruction=["\n\n".join(system_parts)] if system_parts else None,
    )
    chat = model.start_chat(history=prior)
    response = chat.send_message(
        last_user,
        generation_config=GenerationConfig(max_output_tokens=max_tokens, temperature=0.25),
    )
    _track_usage(tenant_id, response)
    return (response.text or "").strip()
