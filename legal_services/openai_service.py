import json
import os
import re
import time

from openai import OpenAI, RateLimitError

_client = None


def llm_provider() -> str:
    return (os.environ.get("LLM_PROVIDER") or "azure").strip().lower()


def active_model_label() -> str:
    if llm_provider() == "vertex":
        from legal_services.vertex_ai_service import model_id

        return model_id()
    return os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-5.4-mini")


def is_configured() -> bool:
    if llm_provider() == "vertex":
        from legal_services import vertex_ai_service as vertex

        return vertex.is_configured()
    return bool(os.environ.get("AZURE_OPENAI_API_KEY"))


def get_client() -> OpenAI:
    global _client
    if _client is None:
        if not os.environ.get("AZURE_OPENAI_API_KEY"):
            raise RuntimeError("AZURE_OPENAI_API_KEY no configurada.")
        _client = OpenAI(
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            base_url=os.environ.get(
                "AZURE_OPENAI_ENDPOINT",
                "https://pruebaiabech.openai.azure.com/openai/v1",
            ),
        )
    return _client


def _track_usage_openai(tenant_id: str | None, response) -> None:
    if not tenant_id or not response or not getattr(response, "usage", None):
        return
    from legal_services.usage_service import record_token_usage

    u = response.usage
    record_token_usage(
        tenant_id,
        total=int(getattr(u, "total_tokens", 0) or 0),
        prompt=int(getattr(u, "prompt_tokens", 0) or 0),
        completion=int(getattr(u, "completion_tokens", 0) or 0),
    )


def chat_completion_messages(
    messages: list[dict], max_tokens: int = 3500, tenant_id: str | None = None
) -> str:
    if llm_provider() == "vertex":
        from legal_services import vertex_ai_service as vertex

        return vertex.chat_completion_messages(messages, max_tokens=max_tokens, tenant_id=tenant_id)

    client = get_client()
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-5.4-mini")
    last_exc = None
    for attempt in range(4):
        try:
            response = client.chat.completions.create(
                model=deployment,
                messages=messages,
                max_completion_tokens=max_tokens,
                temperature=0.25,
            )
            _track_usage_openai(tenant_id, response)
            return response.choices[0].message.content or ""
        except RateLimitError as exc:
            last_exc = exc
            if attempt == 3:
                raise RuntimeError(
                    "Límite de uso de IA alcanzado. Espere un minuto e intente de nuevo."
                ) from exc
            time.sleep(2**attempt + 1)
    if last_exc:
        raise last_exc
    return ""


def chat_completion(
    system_prompt: str, user_content: str, max_tokens: int = 3500, tenant_id: str | None = None
) -> str:
    if llm_provider() == "vertex":
        from legal_services import vertex_ai_service as vertex

        return vertex.chat_completion(
            system_prompt, user_content, max_tokens=max_tokens, tenant_id=tenant_id
        )

    client = get_client()
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-5.4-mini")
    payload = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
    last_exc = None
    for attempt in range(4):
        try:
            response = client.chat.completions.create(
                model=deployment,
                messages=payload,
                max_completion_tokens=max_tokens,
                temperature=0.2,
            )
            _track_usage_openai(tenant_id, response)
            return response.choices[0].message.content or ""
        except RateLimitError as exc:
            last_exc = exc
            if attempt == 3:
                raise RuntimeError(
                    "Límite de uso de IA alcanzado. Espere un minuto e intente de nuevo."
                ) from exc
            time.sleep(2**attempt + 1)
    if last_exc:
        raise last_exc
    return ""


def parse_json_response(text: str) -> dict:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise
