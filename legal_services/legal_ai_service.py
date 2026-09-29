import json

from pathlib import Path



from legal_prompts.legal_analysis import LEGAL_AI_SYSTEM_PROMPT

from legal_services.document_reader import collect_documents_from_dirs, collect_documents_from_files

from legal_services.intake_service import load_ramas

from legal_services.openai_service import chat_completion, is_configured, parse_json_response

from legal_services.tenant_storage import _safe_name, tenant_root





def _rama_checklist(rama_id: str) -> list[str]:

    for r in load_ramas():

        if r.get("id") == rama_id:

            return r.get("documentos_minimos") or []

    return []





def _collect_case_documents(tenant_id: str, caso: dict) -> list[dict]:

    root = tenant_root(tenant_id)

    explicit_files: list[Path] = []

    dirs: list[Path] = []



    case_id = caso.get("case_id")

    if case_id:

        case_doc = root / "casos" / _safe_name(case_id) / "documentos"

        dirs.append(case_doc)

        for sub in ("marco-trabajo", "reglamento", "contratos", "general"):

            dirs.append(case_doc / sub)



    client_id = caso.get("client_id") or caso.get("cliente_nombre")

    if client_id:

        dirs.append(root / "clientes" / _safe_name(client_id) / "05-documentos")



    empresa_id = caso.get("empresa_id") or caso.get("empresa_nombre")

    if empresa_id:

        emp = root / "empresas" / _safe_name(empresa_id)

        dirs.extend([

            emp / "marco-legal-interno",

            emp / "politicas-internas",

            emp / "contratos-laborales",

            emp / "documentos",

        ])



    dirs.append(root / "clientes" / "uploads" / "05-documentos")

    dirs.append(root / "uploads" / "pendientes")



    for doc in caso.get("documentos") or []:

        rel = doc.get("path") if isinstance(doc, dict) else doc

        if not rel:

            continue

        p = Path(rel)

        if not p.is_absolute():

            p = root / rel.replace("\\", "/")

        if p.is_file():

            explicit_files.append(p)

        elif p.parent.exists():

            dirs.append(p.parent)



    context = " ".join(
        filter(
            None,
            [
                caso.get("hechos", ""),
                caso.get("titulo", ""),
                caso.get("rama_nombre", ""),
                " ".join(p.get("nombre", "") for p in (caso.get("partes") or [])),
            ],
        )
    )

    by_name: dict[str, dict] = {}

    for item in collect_documents_from_files(explicit_files, context):

        by_name[item["nombre"]] = item

    for item in collect_documents_from_dirs(dirs, context):

        by_name[item["nombre"]] = item

    return list(by_name.values())





def _build_user_prompt(caso: dict, documents: list[dict]) -> str:

    checklist = _rama_checklist(caso.get("rama_id", ""))

    docs_block = ""

    if documents:

        for d in documents:

            orig = d.get("caracteres_originales")
            meta = f" ({orig} caracteres en original; texto preparado para IA)" if orig else ""
            docs_block += f"\n\n--- DOCUMENTO: {d['nombre']}{meta} ---\n{d['contenido'][:80000]}"

    else:

        docs_block = "\n(SIN DOCUMENTOS LEGIBLES — el abogado cargó archivos pero no se pudieron leer. Indique qué falta.)"



    return f"""CASO (solo contexto):

- Título: {caso.get('titulo')}

- Cliente: {caso.get('cliente_nombre')}

- Empresa: {caso.get('empresa_nombre') or 'N/A'}

- Rama: {caso.get('rama_nombre') or caso.get('rama_id')}

- Hechos declarados: {caso.get('hechos')}

- Partes: {json.dumps(caso.get('partes') or [], ensure_ascii=False)}



CHECKLIST DOCUMENTAL DE LA RAMA:

{json.dumps(checklist, ensure_ascii=False)}



DOCUMENTOS LEGALES CARGADOS (ANALICE ESTO EN PROFUNDIDAD — reglamento, marco de trabajo, contratos):

{docs_block}



INSTRUCCIONES PRIORITARIAS:

1. Lea TODO el texto del documento provisto (incluye capítulos extraídos con artículos completos).

2. NO diga que un capítulo "no fue transcrito" o "solo aparece en el índice" si el articulado está en el texto provisto.

3. Cite SIEMPRE número de artículo y capítulo (ej. "Artículo 107", "Capítulo XXIII") al analizar deberes, prohibiciones, faltas, sanciones y procedimiento disciplinario.

4. Para casos laborales revise obligatoriamente (si están en el texto): Cap. XVIII deberes, Cap. XXII prohibiciones, Cap. XXIII escala de faltas, Cap. XXIV procedimiento sancionatorio, y normas sobre alcohol/horario/asistencia.

5. Contraste documento vs hechos vs CST y reforma laboral colombiana.

6. En reglamento_empresa use clausula_o_politica con formato "Art. X - Cap. Y: ...".

7. Marque checklist presente/faltante/parcial con evidencia documental citada.

"""





def run_ai_analysis(tenant_id: str, caso: dict) -> dict:

    if not is_configured():

        return {

            "ia_disponible": False,

            "error": "Configure AZURE_OPENAI_API_KEY en el archivo .env para activar análisis con IA.",

        }



    documents = _collect_case_documents(tenant_id, caso)

    if not documents:

        return {

            "ia_disponible": False,

            "error": "No se encontraron documentos para analizar. Suba el marco/reglamento de trabajo en la pestaña Análisis.",

            "documentos_analizados": [],

        }



    user_prompt = _build_user_prompt(caso, documents)

    raw = chat_completion(LEGAL_AI_SYSTEM_PROMPT, user_prompt, max_tokens=6500, tenant_id=tenant_id)

    parsed = parse_json_response(raw)



    result = {

        "ia_disponible": True,

        "modelo": __import__("os").environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-5.4-mini"),

        "documentos_analizados": [d["nombre"] for d in documents],

        **parsed,

    }



    case_dir = tenant_root(tenant_id) / "casos" / _safe_name(caso["case_id"])

    (case_dir / "analisis" / "ia_analisis.json").write_text(

        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"

    )

    return result





def merge_ai_into_case(caso: dict, ai: dict) -> dict:

    if not ai.get("ia_disponible"):

        caso["analisis_ia"] = ai

        return caso



    caso["analisis_ia"] = ai

    if ai.get("borrador_comunicacion_cliente"):

        caso["borrador_comunicacion"] = ai["borrador_comunicacion_cliente"]



    legacy = caso.get("analisis_legal") or {}

    legacy["analisis_a_favor_cliente"] = ai.get("a_favor_cliente") or legacy.get("analisis_a_favor_cliente", [])

    legacy["analisis_en_contra"] = ai.get("en_contra_cliente") or legacy.get("analisis_en_contra", [])

    legacy["pasos_sugeridos"] = [

        f"{a.get('prioridad', '')}. {a.get('accion', '')} — {a.get('fundamento', '')}"

        for a in (ai.get("acciones_recomendadas") or [])

    ]

    caso["analisis_legal"] = legacy

    caso["estado"] = "en_analisis"

    return caso


