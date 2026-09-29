import json
import os
import re
import time

from openai import OpenAI, RateLimitError

_client = None


def is_configured() -> bool:
    return bool(os.environ.get("AZURE_OPENAI_API_KEY"))


def get_client() -> OpenAI:
    global _client
    if _client is None:
        if not is_configured():
            raise RuntimeError("AZURE_OPENAI_API_KEY no configurada.")
        _client = OpenAI(
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            base_url=os.environ.get(
                "AZURE_OPENAI_ENDPOINT",
                "https://pruebaiabech.openai.azure.com/openai/v1",
            ),
        )
    return _client


def _track_usage(tenant_id: str | None, response) -> None:
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
            _track_usage(tenant_id, response)
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
            _track_usage(tenant_id, response)
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
