import json
import shutil
from datetime import datetime, timezone
from pathlib import Path



from legal_services.colombia_law import (

    build_legal_analysis,

    draft_client_communication,

    preliminary_viability,

)

from legal_services.legal_ai_service import merge_ai_into_case, run_ai_analysis

from legal_services.openai_service import is_configured

from legal_services.tenant_storage import _safe_name, ensure_client_structure, ensure_company_structure, tenant_root

from legal_services.word_report import generate_analysis_docx





def case_dir(tenant_id: str, case_id: str) -> Path:

    return tenant_root(tenant_id) / "casos" / _safe_name(case_id)





def get_case(tenant_id: str, case_id: str) -> dict | None:

    path = case_dir(tenant_id, case_id) / "caso.json"

    if not path.exists():

        return None

    return json.loads(path.read_text(encoding="utf-8"))


def delete_case(tenant_id: str, case_id: str) -> bool:
    path = case_dir(tenant_id, case_id).resolve()
    casos_root = (tenant_root(tenant_id) / "casos").resolve()
    try:
        path.relative_to(casos_root)
    except ValueError:
        return False
    if not path.is_dir():
        return False
    shutil.rmtree(path)
    return True





def analysis_docx_path(tenant_id: str, case_id: str) -> Path:

    return case_dir(tenant_id, case_id) / "analisis" / f"informe_{_safe_name(case_id)}.docx"





def save_case(tenant_id: str, caso: dict) -> dict:

    cid = caso["case_id"]

    caso["actualizado"] = datetime.now(timezone.utc).isoformat()

    case_path = case_dir(tenant_id, cid)

    case_path.mkdir(parents=True, exist_ok=True)

    for sub in ("hechos", "partes", "documentos", "analisis", "borradores"):

        (case_path / sub).mkdir(exist_ok=True)

    (case_path / "caso.json").write_text(json.dumps(caso, ensure_ascii=False, indent=2), encoding="utf-8")

    docx = generate_analysis_docx(caso, analysis_docx_path(tenant_id, cid))

    caso["informe_word"] = str(docx.relative_to(tenant_root(tenant_id)))

    (case_path / "caso.json").write_text(json.dumps(caso, ensure_ascii=False, indent=2), encoding="utf-8")

    return caso





def finalize_case_analysis(tenant_id: str, payload: dict, use_ai: bool = True) -> dict:

    partes = payload.get("partes", [])

    viability = preliminary_viability(

        payload.get("rama_id", ""),

        payload.get("hechos", ""),

        payload.get("plazo_urgente"),

    )

    analysis = build_legal_analysis(payload.get("rama_id", ""), payload.get("hechos", ""), partes)

    payload["viabilidad"] = viability

    payload["analisis_legal"] = analysis

    payload["borrador_comunicacion"] = draft_client_communication(payload, analysis)



    if use_ai and is_configured() and payload.get("case_id"):

        try:

            ai = run_ai_analysis(tenant_id, payload)

            payload = merge_ai_into_case(payload, ai)

        except Exception as exc:

            payload["analisis_ia"] = {"ia_disponible": False, "error": str(exc)}



    return payload





def analyze_case_with_ai(tenant_id: str, case_id: str) -> dict | None:

    caso = get_case(tenant_id, case_id)

    if not caso:

        return None

    ai = run_ai_analysis(tenant_id, caso)

    caso = merge_ai_into_case(caso, ai)

    return save_case(tenant_id, caso)





def update_case(tenant_id: str, case_id: str, payload: dict, regenerate: bool = True) -> dict | None:

    existing = get_case(tenant_id, case_id)

    if not existing:

        return None

    merged = {**existing, **payload, "case_id": case_id}

    if payload.get("cliente_nombre"):

        ensure_client_structure(tenant_id, merged.get("client_id", case_id), merged["cliente_nombre"])

    if merged.get("empresa_nombre"):

        ensure_company_structure(

            tenant_id,

            merged.get("empresa_id", merged["empresa_nombre"]),

            merged["empresa_nombre"],

        )

    if regenerate:
        merged = finalize_case_analysis(tenant_id, merged, use_ai=False)
        from legal_services.intake_service import _relocate_documents
        _relocate_documents(tenant_id, merged)

    return save_case(tenant_id, merged)


