import json
from datetime import datetime, timezone

from legal_services.env_paths import environment_data_root


def _usage_path():
    path = environment_data_root() / "token_usage.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load() -> dict:
    path = _usage_path()
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save(data: dict) -> None:
    _usage_path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def record_token_usage(tenant_id: str, *, total: int = 0, prompt: int = 0, completion: int = 0) -> None:
    tid = (tenant_id or "").strip().lower()
    if not tid or total <= 0:
        return
    data = _load()
    entry = data.get(tid) or {
        "total_tokens": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "calls": 0,
    }
    entry["total_tokens"] = int(entry.get("total_tokens") or 0) + int(total)
    entry["prompt_tokens"] = int(entry.get("prompt_tokens") or 0) + int(prompt)
    entry["completion_tokens"] = int(entry.get("completion_tokens") or 0) + int(completion)
    entry["calls"] = int(entry.get("calls") or 0) + 1
    entry["ultimo_uso"] = datetime.now(timezone.utc).isoformat()
    data[tid] = entry
    _save(data)


def get_usage(tenant_id: str) -> dict:
    tid = (tenant_id or "").strip().lower()
    entry = _load().get(tid) or {}
    return {
        "total_tokens": int(entry.get("total_tokens") or 0),
        "prompt_tokens": int(entry.get("prompt_tokens") or 0),
        "completion_tokens": int(entry.get("completion_tokens") or 0),
        "calls": int(entry.get("calls") or 0),
        "ultimo_uso": entry.get("ultimo_uso"),
    }


def all_usage() -> dict:
    return _load()
