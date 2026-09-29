import json
import shutil
from pathlib import Path

from legal_services.tenant_storage import _safe_name, create_case, ensure_client_structure, ensure_company_structure, tenant_root

ROOT = Path(__file__).resolve().parent.parent
RAMAS_PATH = ROOT / "config" / "ramas_derecho_colombia.json"


def load_ramas() -> list[dict]:
    return json.loads(RAMAS_PATH.read_text(encoding="utf-8"))


def _relocate_documents(tenant_id: str, caso: dict) -> None:
    root = tenant_root(tenant_id)
    case_id = _safe_name(caso["case_id"])
    dest_base = root / "casos" / case_id / "documentos" / "marco-trabajo"
    dest_base.mkdir(parents=True, exist_ok=True)
    updated = []
    for doc in caso.get("documentos") or []:
        rel = (doc.get("path") or "").replace("\\", "/")
        src = root / rel if rel else None
        if src and src.is_file():
            dest = dest_base / src.name
            if src.resolve() != dest.resolve():
                shutil.copy2(src, dest)
            rel_new = str(dest.relative_to(root)).replace("\\", "/")
            updated.append({**doc, "path": rel_new, "tipo": doc.get("tipo") or "marco_trabajo"})
        else:
            updated.append(doc)
    caso["documentos"] = updated


def process_intake(tenant_id: str, payload: dict) -> dict:
    client_id = payload.get("client_id") or payload.get("cliente_nombre", "cliente")
    ensure_client_structure(tenant_id, client_id, payload.get("cliente_nombre", client_id))

    if payload.get("empresa_nombre"):
        ensure_company_structure(
            tenant_id,
            payload.get("empresa_id", payload["empresa_nombre"]),
            payload["empresa_nombre"],
        )

    caso = create_case(tenant_id, payload)
    _relocate_documents(tenant_id, caso)
    case_dir = tenant_root(tenant_id) / "casos" / _safe_name(caso["case_id"])
    (case_dir / "borradores").mkdir(exist_ok=True)

    from legal_services.case_service import finalize_case_analysis, save_case

    caso = finalize_case_analysis(tenant_id, caso, use_ai=False)
    if caso.get("borrador_comunicacion"):
        (case_dir / "borradores" / "comunicacion_cliente.txt").write_text(
            caso["borrador_comunicacion"], encoding="utf-8"
        )
    return save_case(tenant_id, caso)


def save_intake_draft(tenant_id: str, payload: dict, case_id: str | None = None) -> dict:
    """Guarda progreso parcial del wizard sin regenerar análisis completo."""
    from legal_services.case_service import save_case, update_case

    data = dict(payload)
    data["estado"] = "borrador"
    cid = case_id or data.get("case_id")

    if cid:
        updated = update_case(tenant_id, cid, data, regenerate=False)
        if not updated:
            raise ValueError("Caso no encontrado")
        return updated

    client_id = data.get("client_id") or data.get("cliente_nombre") or "cliente"
    if data.get("cliente_nombre"):
        ensure_client_structure(tenant_id, client_id, data["cliente_nombre"])
    if data.get("empresa_nombre"):
        ensure_company_structure(
            tenant_id,
            data.get("empresa_id", data["empresa_nombre"]),
            data["empresa_nombre"],
        )

    caso = create_case(tenant_id, data)
    _relocate_documents(tenant_id, caso)
    return save_case(tenant_id, caso)
