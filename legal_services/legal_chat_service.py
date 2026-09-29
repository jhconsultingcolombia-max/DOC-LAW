import json
from datetime import datetime, timezone
from pathlib import Path

from legal_prompts.legal_chat import LEGAL_CHAT_SYSTEM_PROMPT
from legal_services.case_service import get_case
from legal_services.document_reader import collect_documents_from_dirs
from legal_services.intake_service import load_ramas
from legal_services.legal_ai_service import _collect_case_documents
from legal_services.openai_service import chat_completion_messages, is_configured
from legal_services.tenant_storage import _safe_name, list_cases, tenant_root

MAX_HISTORY = 20
MAX_DOC_CHARS_CHAT = 55000


def _chat_file(tenant_id: str, case_id: str | None, *, law_only: bool = False) -> Path:
    base = tenant_root(tenant_id) / "chat"
    base.mkdir(parents=True, exist_ok=True)
    if law_only:
        name = "solo-ley"
    elif case_id:
        name = _safe_name(case_id)
    else:
        name = "general"
    return base / f"{name}.json"


def get_chat_history(
    tenant_id: str, case_id: str | None = None, *, law_only: bool = False
) -> list[dict]:
    path = _chat_file(tenant_id, case_id, law_only=law_only)
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def save_chat_turn(
    tenant_id: str,
    case_id: str | None,
    user_msg: str,
    assistant_msg: str,
    *,
    law_only: bool = False,
) -> list[dict]:
    history = get_chat_history(tenant_id, case_id, law_only=law_only)
    ts = datetime.now(timezone.utc).isoformat()
    history.append({"role": "user", "content": user_msg, "ts": ts})
    history.append({"role": "assistant", "content": assistant_msg, "ts": ts})
    history = history[-MAX_HISTORY * 2 :]
    _chat_file(tenant_id, case_id, law_only=law_only).write_text(
        json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return history


def clear_chat_history(
    tenant_id: str, case_id: str | None = None, *, law_only: bool = False
) -> None:
    path = _chat_file(tenant_id, case_id, law_only=law_only)
    if path.exists():
        path.unlink()


def _collect_tenant_documents(tenant_id: str, case_id: str | None, focus: str) -> list[dict]:
    if case_id:
        caso = get_case(tenant_id, case_id)
        if caso:
            return _collect_case_documents(tenant_id, caso)

    root = tenant_root(tenant_id)
    by_name: dict[str, dict] = {}
    for caso in list_cases(tenant_id)[:12]:
        for item in _collect_case_documents(tenant_id, caso):
            by_name[item["nombre"]] = item

    dirs = [
        root / "empresas",
        root / "clientes",
        root / "uploads" / "pendientes",
    ]
    for item in collect_documents_from_dirs(dirs, focus):
        by_name[item["nombre"]] = item

    return list(by_name.values())


def _build_context_block(tenant_id: str, case_id: str | None, focus: str) -> tuple[str, list[str]]:
    documents = _collect_tenant_documents(tenant_id, case_id, focus)
    if not documents:
        return "(Sin documentos cargados en el tenant/caso.)", []

    names = [d["nombre"] for d in documents]
    parts = []
    total = 0
    for doc in documents:
        chunk = doc["contenido"]
        if total + len(chunk) > MAX_DOC_CHARS_CHAT:
            chunk = chunk[: max(0, MAX_DOC_CHARS_CHAT - total)]
        if not chunk.strip():
            continue
        orig = doc.get("caracteres_originales")
        meta = f" ({orig} caracteres en original)" if orig else ""
        parts.append(f"--- {doc['nombre']}{meta} ---\n{chunk}")
        total += len(chunk)
        if total >= MAX_DOC_CHARS_CHAT:
            break

    return "\n\n".join(parts), names


def _build_case_summary(tenant_id: str, case_id: str | None) -> str:
    if not case_id:
        return "Consulta general del despacho (sin caso vinculado)."
    caso = get_case(tenant_id, case_id)
    if not caso:
        return f"Caso {case_id} no encontrado."
    return json.dumps(
        {
            "case_id": caso.get("case_id"),
            "titulo": caso.get("titulo"),
            "rama": caso.get("rama_nombre") or caso.get("rama_id"),
            "hechos": caso.get("hechos"),
            "partes": caso.get("partes"),
            "empresa": caso.get("empresa_nombre"),
        },
        ensure_ascii=False,
        indent=2,
    )


def get_chat_meta(
    tenant_id: str,
    case_id: str | None = None,
    *,
    use_documents: bool = True,
    law_only: bool = False,
) -> dict:
    if law_only:
        doc_names = []
    elif use_documents:
        _, doc_names = _build_context_block(tenant_id, case_id, "")
    else:
        doc_names = []
    return {
        "documentos_disponibles": doc_names,
        "use_documents": use_documents and not law_only,
        "law_only": law_only,
        "case_id": None if law_only else case_id,
        "history": get_chat_history(tenant_id, case_id, law_only=law_only),
    }


def run_legal_chat(
    tenant_id: str,
    message: str,
    case_id: str | None = None,
    include_history: bool = True,
    use_documents: bool = True,
    law_only: bool = False,
) -> dict:
    if not is_configured():
        return {
            "ok": False,
            "error": "IA no configurada. Agregue AZURE_OPENAI_API_KEY en el archivo .env",
        }

    message = (message or "").strip()
    if not message:
        return {"ok": False, "error": "Escriba una pregunta."}

    if law_only:
        doc_names = []
        docs_section = (
            "DOCUMENTOS Y CASO: ninguno vinculado. Modo consulta general de derecho colombiano."
        )
        case_summary = (
            "Sin expediente ni archivos. Responda como asistente jurídico general (Colombia)."
        )
        use_documents = False
        case_id = None
    elif use_documents:
        docs_text, doc_names = _build_context_block(tenant_id, case_id, message)
        docs_section = f"DOCUMENTOS LEGALES DISPONIBLES (prioridad para responder):\n{docs_text}"
        case_summary = _build_case_summary(tenant_id, case_id)
    else:
        doc_names = []
        docs_section = (
            "DOCUMENTOS LEGALES: (modo sin archivos — no se inyectó contenido de PDF/Word al contexto). "
            "Responda con derecho colombiano vigente, el resumen del caso si aplica, y buenas prácticas procesales."
        )
        case_summary = _build_case_summary(tenant_id, case_id)

    ramas = [r.get("nombre") for r in load_ramas()]

    system_content = f"""{LEGAL_CHAT_SYSTEM_PROMPT}

RAMAS DEL DESPACHO (referencia): {", ".join(ramas)}

CONTEXTO DEL CASO (si aplica):
{case_summary}

{docs_section}
"""

    messages = [{"role": "system", "content": system_content}]

    if include_history:
        for turn in get_chat_history(tenant_id, case_id, law_only=law_only)[-MAX_HISTORY:]:
            messages.append({"role": turn["role"], "content": turn["content"]})

    messages.append({"role": "user", "content": message})

    try:
        reply = chat_completion_messages(messages, max_tokens=3500, tenant_id=tenant_id)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    history = save_chat_turn(tenant_id, case_id, message, reply, law_only=law_only)
    return {
        "ok": True,
        "reply": reply,
        "documentos_disponibles": doc_names,
        "use_documents": use_documents,
        "law_only": law_only,
        "case_id": case_id,
        "history": history,
    }
