import hashlib

from legal_services.case_service import get_case, save_case
from legal_services.rama_judicial_service import consultar_radicado, normalize_radicado
from legal_services.tenant_storage import list_cases

LITIGACION_TIPOS = ("demanda", "poder", "pruebas", "memorial")


def actuacion_id(numero: str, item: dict) -> str:
    if item.get("actuacion_id"):
        return str(item["actuacion_id"])
    raw = "|".join(
        [
            normalize_radicado(numero),
            (item.get("fecha") or ""),
            (item.get("actuacion") or "").strip(),
            (item.get("anotacion") or "").strip(),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _merge_traza(numero: str, new_traza: list[dict], old_traza: list[dict] | None) -> list[dict]:
    old_read: dict[str, bool] = {}
    for item in old_traza or []:
        key = actuacion_id(numero, item)
        leida = item.get("leida")
        old_read[key] = True if leida is None else bool(leida)

    merged: list[dict] = []
    for item in new_traza or []:
        key = actuacion_id(numero, item)
        if key in old_read:
            leida = old_read[key]
        else:
            leida = False
        merged.append(
            {
                **item,
                "actuacion_id": key,
                "leida": leida,
                "documentos_cpnu": item.get("documentos_cpnu")
                if item.get("documentos_cpnu") is not None
                else next(
                    (
                        o.get("documentos_cpnu")
                        for o in (old_traza or [])
                        if actuacion_id(numero, o) == key
                    ),
                    None,
                ),
            }
        )
    return merged


def _merge_radicado(existing: dict | None, fresh: dict) -> dict:
    numero = fresh["numero"]
    old_traza = (existing or {}).get("traza")
    traza = _merge_traza(numero, fresh.get("traza") or [], old_traza)

    base = dict(existing or {})
    base.update(
        {
            "numero": numero,
            "ultima_actuacion": fresh.get("ultima_actuacion"),
            "fecha_radicacion": fresh.get("fecha_radicacion"),
            "despacho": fresh.get("despacho"),
            "departamento": fresh.get("departamento"),
            "sujetos_procesales": fresh.get("sujetos_procesales"),
            "traza": traza,
            "id_proceso": fresh.get("id_proceso"),
            "url_oficial": fresh.get("url_oficial"),
            "consultado_en": fresh.get("consultado_en"),
        }
    )
    return base


def list_radicados(tenant_id: str, case_id: str) -> list[dict]:
    caso = get_case(tenant_id, case_id)
    if not caso:
        return []
    return caso.get("radicados") or []


def add_radicado(tenant_id: str, case_id: str, numero: str, refresh: bool = True) -> dict:
    caso = get_case(tenant_id, case_id)
    if not caso:
        return {"ok": False, "error": "Caso no encontrado"}

    numero = normalize_radicado(numero)
    radicados = caso.get("radicados") or []
    existing = next((r for r in radicados if r.get("numero") == numero), None)

    entry = dict(existing or {"numero": numero})
    if refresh:
        result = consultar_radicado(numero)
        if not result.get("ok"):
            return result
        entry = _merge_radicado(entry, result)

    if not existing:
        radicados.append(entry)
    else:
        radicados = [_merge_radicado(r, entry) if r.get("numero") == numero else r for r in radicados]

    caso["radicados"] = radicados
    save_case(tenant_id, caso)
    return {"ok": True, "radicado": entry, "caso": caso}


def refresh_radicados(tenant_id: str, case_id: str) -> dict:
    caso = get_case(tenant_id, case_id)
    if not caso:
        return {"ok": False, "error": "Caso no encontrado"}

    radicados = caso.get("radicados") or []
    if not radicados:
        return {"ok": False, "error": "No hay radicados en el caso."}

    updated = []
    errors = []
    for item in radicados:
        numero = item.get("numero")
        if not numero:
            continue
        result = consultar_radicado(numero)
        if result.get("ok"):
            updated.append(_merge_radicado(item, result))
        else:
            errors.append({"numero": numero, "error": result.get("error")})
            updated.append(item)

    caso["radicados"] = updated
    save_case(tenant_id, caso)
    return {"ok": True, "radicados": updated, "errors": errors, "caso": caso}


def set_actuacion_leida(
    tenant_id: str, case_id: str, numero: str, actuacion_id_value: str, leida: bool
) -> dict:
    caso = get_case(tenant_id, case_id)
    if not caso:
        return {"ok": False, "error": "Caso no encontrado"}

    numero = normalize_radicado(numero)
    found = False
    radicados = caso.get("radicados") or []
    for rad in radicados:
        if normalize_radicado(rad.get("numero", "")) != numero:
            continue
        traza = rad.get("traza") or []
        for item in traza:
            if item.get("actuacion_id") == actuacion_id_value or actuacion_id(numero, item) == actuacion_id_value:
                item["actuacion_id"] = actuacion_id(numero, item)
                item["leida"] = bool(leida)
                found = True
                break
        rad["traza"] = traza
        break

    if not found:
        return {"ok": False, "error": "Actuación no encontrada."}

    caso["radicados"] = radicados
    save_case(tenant_id, caso)
    return {"ok": True, "caso": caso, "no_leidos": count_unread_actuaciones(tenant_id)}


def iter_unread_actuaciones(tenant_id: str) -> list[dict]:
    items: list[dict] = []
    for caso in list_cases(tenant_id):
        case_id = caso.get("case_id")
        titulo = caso.get("titulo") or case_id
        for rad in caso.get("radicados") or []:
            numero = rad.get("numero") or ""
            for act in rad.get("traza") or []:
                if act.get("leida") is False:
                    aid = actuacion_id(numero, act)
                    items.append(
                        {
                            "case_id": case_id,
                            "titulo": titulo,
                            "numero": numero,
                            "actuacion_id": aid,
                            "fecha": act.get("fecha"),
                            "actuacion": act.get("actuacion"),
                            "anotacion": act.get("anotacion"),
                        }
                    )
    items.sort(key=lambda x: (x.get("fecha") or ""), reverse=True)
    return items


def count_unread_actuaciones(tenant_id: str) -> int:
    return len(iter_unread_actuaciones(tenant_id))


def refresh_all_tenant_radicados(tenant_id: str) -> dict:
    refreshed_cases = 0
    errors: list[dict] = []
    for caso in list_cases(tenant_id):
        case_id = caso.get("case_id")
        if not case_id or not (caso.get("radicados") or []):
            continue
        result = refresh_radicados(tenant_id, case_id)
        if result.get("ok"):
            refreshed_cases += 1
            errors.extend(result.get("errors") or [])
        else:
            errors.append({"case_id": case_id, "error": result.get("error")})

    return {
        "ok": True,
        "casos_actualizados": refreshed_cases,
        "no_leidos": count_unread_actuaciones(tenant_id),
        "errors": errors,
    }


def documentos_por_tipo(caso: dict) -> dict[str, list]:
    grouped = {t: [] for t in LITIGACION_TIPOS}
    for doc in caso.get("documentos") or []:
        tipo = (doc.get("tipo") or "general").lower()
        if tipo in grouped:
            grouped[tipo].append(doc)
    return grouped
