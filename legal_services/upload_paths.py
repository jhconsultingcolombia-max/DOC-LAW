from legal_services.tenant_storage import _safe_name


def resolve_upload_rel_path(
    *,
    case_id: str | None = None,
    client_id: str | None = None,
    empresa_id: str | None = None,
    tipo: str = "general",
) -> str:
    tipo = (tipo or "general").strip().lower()
    mapping = {
        "marco_trabajo": "marco-trabajo",
        "reglamento": "reglamento",
        "contrato": "contratos",
        "demanda": "demanda",
        "poder": "poder",
        "pruebas": "pruebas",
        "memorial": "memoriales",
        "general": "general",
    }
    folder = mapping.get(tipo, "general")

    if case_id:
        return f"casos/{_safe_name(case_id)}/documentos/{folder}"
    if tipo in {"marco_trabajo", "reglamento", "contrato"} and empresa_id:
        empresa_map = {
            "marco_trabajo": "marco-legal-interno",
            "reglamento": "politicas-internas",
            "contrato": "contratos-laborales",
        }
        return f"empresas/{_safe_name(empresa_id)}/{empresa_map.get(tipo, 'documentos')}"
    if client_id:
        return f"clientes/{_safe_name(client_id)}/05-documentos"
    return "uploads/pendientes"
