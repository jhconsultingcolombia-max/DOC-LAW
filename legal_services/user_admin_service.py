import csv
import os

from legal_services.auth_service import load_users
from legal_services.env_paths import usuarios_csv_path, usuarios_xlsx_path
from legal_services.tenant_storage import list_cases
from legal_services.usage_service import get_usage

CSV_FIELDS = ["usuario", "clave", "tenant_id", "nombre_despacho", "max_casos", "admin"]


def _truthy(val) -> bool:
    return str(val or "").strip().lower() in ("1", "true", "yes", "si", "sí", "admin")


def _normalize_row(row: dict) -> dict:
    user = str(row.get("usuario") or "").strip()
    return {
        "usuario": user,
        "clave": str(row.get("clave") or "").strip(),
        "tenant_id": str(row.get("tenant_id") or user).strip().lower(),
        "nombre_despacho": str(row.get("nombre_despacho") or user).strip(),
        "max_casos": str(row.get("max_casos") or "").strip(),
        "admin": "1" if _truthy(row.get("admin")) else "0",
    }


def is_admin_user(username: str) -> bool:
    user = (username or "").strip()
    fallback = (os.environ.get("LEGAL_ADMIN_USER") or "david").strip().lower()
    if user.lower() == fallback:
        return True
    for row in load_users():
        if str(row.get("usuario", "")).strip() == user:
            return _truthy(row.get("admin"))
    return False


def _max_casos_limit(row: dict) -> int | None:
    raw = str(row.get("max_casos") or "").strip()
    if not raw:
        return None
    try:
        n = int(raw)
        return n if n >= 0 else None
    except ValueError:
        return None


def case_limit_for_tenant(tenant_id: str) -> int | None:
    tid = (tenant_id or "").strip().lower()
    for row in load_users():
        if str(row.get("tenant_id", "")).strip().lower() == tid:
            return _max_casos_limit(row)
    return None


def check_case_limit(tenant_id: str) -> None:
    limit = case_limit_for_tenant(tenant_id)
    if limit is None:
        return
    count = len(list_cases(tenant_id))
    if count >= limit:
        raise ValueError(
            f"Límite de casos alcanzado ({limit}). Contacte al administrador para ampliar su cupo."
        )


def save_users_csv(rows: list[dict]) -> None:
    if usuarios_xlsx_path().is_file():
        raise ValueError("Hay usuarios.xlsx activo; use CSV o elimine el xlsx para administrar desde la app.")
    path = usuarios_csv_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = [_normalize_row(r) for r in rows if _normalize_row(r).get("usuario")]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in normalized:
            writer.writerow({k: row.get(k, "") for k in CSV_FIELDS})


def list_users_overview() -> list[dict]:
    items = []
    for row in load_users():
        n = _normalize_row(row)
        tid = n["tenant_id"]
        usage = get_usage(tid)
        limit = _max_casos_limit(n)
        casos = len(list_cases(tid))
        items.append(
            {
                "usuario": n["usuario"],
                "tenant_id": tid,
                "nombre_despacho": n["nombre_despacho"],
                "max_casos": limit,
                "casos_actuales": casos,
                "admin": n["admin"] == "1",
                "tokens_total": usage["total_tokens"],
                "tokens_llamadas": usage["calls"],
                "ultimo_uso_ia": usage.get("ultimo_uso"),
            }
        )
    return items


def upsert_user(usuario: str, data: dict) -> dict:
    usuario = (usuario or "").strip()
    if not usuario:
        raise ValueError("Usuario requerido.")
    rows = [_normalize_row(r) for r in load_users()]
    idx = next((i for i, r in enumerate(rows) if r["usuario"] == usuario), None)
    if idx is None:
        if not data.get("clave"):
            raise ValueError("Indique contraseña para el usuario nuevo.")
        rows.append(
            _normalize_row(
                {
                    "usuario": usuario,
                    "clave": data.get("clave"),
                    "tenant_id": data.get("tenant_id") or usuario.lower(),
                    "nombre_despacho": data.get("nombre_despacho") or usuario,
                    "max_casos": data.get("max_casos", ""),
                    "admin": data.get("admin", "0"),
                }
            )
        )
    else:
        cur = rows[idx]
        if data.get("clave"):
            cur["clave"] = str(data["clave"]).strip()
        if "nombre_despacho" in data:
            cur["nombre_despacho"] = str(data["nombre_despacho"] or cur["nombre_despacho"]).strip()
        if "tenant_id" in data and data["tenant_id"]:
            cur["tenant_id"] = str(data["tenant_id"]).strip().lower()
        if "max_casos" in data:
            mc = data["max_casos"]
            cur["max_casos"] = "" if mc is None or mc == "" else str(int(mc))
        if "admin" in data:
            cur["admin"] = "1" if _truthy(data["admin"]) else "0"
        rows[idx] = cur

    admins = sum(1 for r in rows if r["admin"] == "1")
    if admins < 1:
        raise ValueError("Debe quedar al menos un administrador.")
    save_users_csv(rows)
    return next(r for r in list_users_overview() if r["usuario"] == usuario)
