import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from legal_services.env_paths import tenants_root

DATA_ROOT = tenants_root()


def _safe_name(value: str) -> str:
    value = (value or "sin-nombre").strip().lower()
    value = re.sub(r"[^a-z0-9\-_]+", "-", value)
    return value[:80] or "sin-nombre"


def tenant_root(tenant_id: str) -> Path:
    path = DATA_ROOT / _safe_name(tenant_id)
    path.mkdir(parents=True, exist_ok=True)
    (path / "empresas").mkdir(exist_ok=True)
    (path / "clientes").mkdir(exist_ok=True)
    (path / "casos").mkdir(exist_ok=True)
    (path / "conflictos").mkdir(exist_ok=True)
    return path


def ensure_client_structure(tenant_id: str, client_id: str, client_name: str) -> Path:
    root = tenant_root(tenant_id) / "clientes" / _safe_name(client_id)
    for folder in (
        "01-identificacion",
        "02-hechos-cronologia",
        "03-partes",
        "04-empresas-vinculadas",
        "05-documentos",
        "06-analisis-legal",
        "07-comunicaciones",
        "08-aprobaciones",
    ):
        (root / folder).mkdir(parents=True, exist_ok=True)
    meta = {
        "client_id": client_id,
        "nombre": client_name,
        "actualizado": datetime.now(timezone.utc).isoformat(),
    }
    (root / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return root


def ensure_company_structure(tenant_id: str, company_id: str, company_name: str) -> Path:
    root = tenant_root(tenant_id) / "empresas" / _safe_name(company_id)
    for folder in (
        "marco-legal-interno",
        "empleados-seguridad-social",
        "contratos-laborales",
        "politicas-internas",
        "documentos",
    ):
        (root / folder).mkdir(parents=True, exist_ok=True)
    meta = {
        "company_id": company_id,
        "nombre": company_name,
        "actualizado": datetime.now(timezone.utc).isoformat(),
    }
    (root / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return root


def create_case(tenant_id: str, payload: dict) -> dict:
    from legal_services.user_admin_service import check_case_limit

    check_case_limit(tenant_id)
    case_id = payload.get("case_id") or str(uuid.uuid4())[:8]
    case_dir = tenant_root(tenant_id) / "casos" / _safe_name(case_id)
    case_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("hechos", "partes", "documentos", "analisis", "borradores"):
        (case_dir / sub).mkdir(exist_ok=True)
    record = {
        "case_id": case_id,
        "creado": datetime.now(timezone.utc).isoformat(),
        "estado": "intake_inicial",
        **payload,
    }
    (case_dir / "caso.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def list_cases(tenant_id: str) -> list[dict]:
    cases_dir = tenant_root(tenant_id) / "casos"
    items = []
    for path in sorted(cases_dir.glob("*/caso.json")):
        try:
            items.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return sorted(items, key=lambda x: x.get("creado", ""), reverse=True)


def save_upload(tenant_id: str, rel_path: str, filename: str, content: bytes) -> str:
    dest_dir = tenant_root(tenant_id) / rel_path
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe = _safe_name(Path(filename).stem) + Path(filename).suffix.lower()
    dest = dest_dir / safe
    dest.write_bytes(content)
    return str(dest.relative_to(tenant_root(tenant_id)))
