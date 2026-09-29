import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

CPNU_BASE = "https://consultaprocesos.ramajudicial.gov.co"
CPNU_API = f"{CPNU_BASE}:448/api/v2"
CPNU_CONSULTA_URL = f"{CPNU_BASE}/Procesos/NumeroRadicacion"

RADICADO_RE = re.compile(r"^\d{23}$")


def _headers() -> dict:
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": CPNU_CONSULTA_URL,
        "Origin": CPNU_BASE,
    }


def _get_json(url: str) -> dict | list:
    req = urllib.request.Request(url, headers=_headers())
    with urllib.request.urlopen(req, timeout=35) as resp:
        return json.loads(resp.read().decode("utf-8", "ignore"))


def _get_bytes(url: str, extra_headers: dict | None = None) -> tuple[bytes, str]:
    hdrs = {**_headers(), "Accept": "application/pdf,application/octet-stream,*/*"}
    if extra_headers:
        hdrs.update(extra_headers)
    req = urllib.request.Request(url, headers=hdrs)
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read(), (resp.headers.get("Content-Type") or "application/octet-stream")


def _post_json(url: str, payload: dict) -> dict | list | bytes:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={**_headers(), "Content-Type": "application/json", "Accept": "application/json,application/pdf,*/*"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        raw = resp.read()
        ctype = resp.headers.get("Content-Type") or ""
        if "pdf" in ctype or "octet-stream" in ctype:
            return raw
        return json.loads(raw.decode("utf-8", "ignore"))


def _fmt_date(value: str | None) -> str | None:
    if not value:
        return None
    return value.split("T")[0] if "T" in value else value[:10]


def normalize_radicado(numero: str) -> str:
    return re.sub(r"\D", "", (numero or "").strip())


def cpnu_proceso_url(id_proceso: int | str | None) -> str:
    if not id_proceso:
        return CPNU_CONSULTA_URL
    return f"{CPNU_BASE}/procesos/{id_proceso}"


def list_documentos_actuacion(id_reg_actuacion: int | str) -> list[dict]:
    url = f"{CPNU_API}/Proceso/DocumentosActuacion/{id_reg_actuacion}?pagina=1"
    try:
        data = _get_json(url)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    docs = []
    for item in data:
        url_descarga = None
        for key in ("urlDocumento", "url", "uriDocumento", "rutaDescarga", "linkDocumento"):
            val = item.get(key)
            if val and isinstance(val, str) and val.strip():
                url_descarga = val.strip()
                break
        docs.append(
            {
                "id_reg_documento": item.get("idRegDocumento"),
                "id_conexion": item.get("idConexion"),
                "guid": item.get("guidDocumento_SXXIW"),
                "nombre": (item.get("nombre") or "documento.pdf").strip(),
                "tipo": (item.get("tipo") or "pdf").lower(),
                "descripcion": (item.get("descripcion") or "").strip(),
                "url_descarga": url_descarga,
            }
        )
    return docs


def _resolve_cpnu_url(path_or_url: str) -> str:
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        return path_or_url
    if path_or_url.startswith("/"):
        return f"{CPNU_BASE}{path_or_url}"
    return f"{CPNU_API}/{path_or_url.lstrip('/')}"


def _post_form(url: str, fields: dict) -> tuple[bytes, str]:
    body = urllib.parse.urlencode({k: v for k, v in fields.items() if v is not None}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            **_headers(),
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/pdf,application/octet-stream,*/*",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read(), (resp.headers.get("Content-Type") or "application/octet-stream")


def descargar_documento_cpnu(doc: dict) -> tuple[bytes, str]:
    id_doc = doc.get("id_reg_documento")
    conn = doc.get("id_conexion")
    guid = doc.get("guid")
    id_actuacion = doc.get("id_reg_actuacion")
    if not id_doc:
        raise ValueError("Documento CPNU sin identificador.")

    # Misma ruta que usa el front oficial CPNU (axios base :448/api/v2).
    official_get = [
        f"{CPNU_API}/Descarga/Documento/{id_doc}",
        f"{CPNU_API}/Descarga/DocumentoActuacion/{id_doc}",
    ]
    if id_actuacion:
        official_get.append(f"{CPNU_API}/Descarga/DocumentoActuacion/{id_actuacion}")
    last_error: Exception | None = None
    for url in official_get:
        try:
            data, ctype = _get_bytes(url)
            if data[:4] == b"%PDF" or "pdf" in ctype or "octet-stream" in ctype:
                return data, "application/pdf" if "pdf" in ctype else ctype
        except Exception as exc:
            last_error = exc

    direct = doc.get("url_descarga")
    if direct:
        try:
            data, ctype = _get_bytes(_resolve_cpnu_url(direct))
            if data[:4] == b"%PDF" or "pdf" in ctype or "octet-stream" in ctype:
                return data, "application/pdf" if "pdf" in ctype else ctype
        except Exception:
            pass

    q = urllib.parse.urlencode(
        {k: v for k, v in [("idRegDocumento", id_doc), ("idConexion", conn), ("guidDocumento_SXXIW", guid)] if v}
    )
    get_urls = [
        f"{CPNU_API}/Proceso/DocumentosActuacion/DescargarDocumento/{id_doc}/{conn}",
        f"{CPNU_API}/Proceso/DocumentosActuacion/DescargarDocumento/{id_doc}",
        f"{CPNU_API}/Proceso/DocumentosActuacion/Descargar/{id_doc}/{conn}",
        f"{CPNU_API}/Proceso/DocumentosActuacion/DescargarDocumento?{q}",
        f"{CPNU_BASE}/Procesos/DescargarDocumento?{q}",
    ]
    if guid:
        get_urls.extend(
            [
                f"{CPNU_API}/Proceso/DocumentosActuacion/DescargarDocumento/{guid}",
                f"{CPNU_API}/Proceso/DocumentosActuacion/DescargarDocumento/{id_doc}/{conn}/{guid}",
            ]
        )

    for url in get_urls:
        try:
            data, ctype = _get_bytes(url)
            if data[:4] == b"%PDF" or "pdf" in ctype:
                return data, "application/pdf"
        except Exception as exc:
            last_error = exc

    post_url = f"{CPNU_API}/Proceso/DocumentosActuacion/DescargarDocumento"
    post_payloads = [
        {"idRegDocumento": id_doc, "idConexion": conn, "guidDocumento_SXXIW": guid},
        {"IdRegDocumento": id_doc, "IdConexion": conn, "GuidDocumento_SXXIW": guid},
    ]
    for payload in post_payloads:
        try:
            result = _post_json(post_url, {k: v for k, v in payload.items() if v is not None})
            if isinstance(result, (bytes, bytearray)) and result[:4] == b"%PDF":
                return bytes(result), "application/pdf"
        except Exception as exc:
            last_error = exc
        try:
            data, ctype = _post_form(post_url, payload)
            if data[:4] == b"%PDF" or "pdf" in ctype:
                return data, "application/pdf"
        except Exception as exc:
            last_error = exc

    raise RuntimeError(
        f"No se pudo descargar el documento desde CPNU. Use «Abrir en CPNU». Detalle: {last_error}"
    )


def consultar_radicado(numero: str) -> dict:
    numero = normalize_radicado(numero)
    if not RADICADO_RE.match(numero):
        return {"ok": False, "error": "El radicado debe tener 23 dígitos numéricos."}

    params = urllib.parse.urlencode(
        {"numero": numero, "SoloActivos": "true", "SoloTerminados": "true", "pagina": "1"}
    )
    url = f"{CPNU_API}/Procesos/Consulta/NumeroRadicacion?{params}"
    try:
        data = _get_json(url)
    except urllib.error.HTTPError as exc:
        return {"ok": False, "error": f"Consulta CPNU falló (HTTP {exc.code})."}
    except Exception as exc:
        return {"ok": False, "error": f"No se pudo consultar la Rama Judicial: {exc}"}

    procesos = data.get("procesos") or []
    if not procesos:
        return {
            "ok": False,
            "error": "Radicado no encontrado en CPNU. Verifique el número en la consulta oficial.",
            "url_oficial": CPNU_CONSULTA_URL,
        }

    proc = procesos[0]
    id_proceso = proc.get("idProceso")
    traza: list[dict] = []
    if id_proceso:
        try:
            act_url = f"{CPNU_API}/Proceso/Actuaciones/{id_proceso}?pagina=1"
            act_data = _get_json(act_url)
            for item in act_data.get("actuaciones") or []:
                id_reg = item.get("idRegActuacion")
                con_docs = bool(item.get("conDocumentos"))
                entry = {
                    "fecha": _fmt_date(item.get("fechaActuacion")),
                    "actuacion": (item.get("actuacion") or "").strip(),
                    "anotacion": (item.get("anotacion") or "").strip(),
                    "id_reg_actuacion": id_reg,
                    "con_documentos": con_docs,
                }
                if con_docs and id_reg:
                    entry["documentos_cpnu"] = [
                        {**d, "id_reg_actuacion": id_reg}
                        for d in list_documentos_actuacion(id_reg)
                    ]
                traza.append(entry)
        except Exception:
            pass

    ultima = _fmt_date(proc.get("fechaUltimaActuacion"))
    return {
        "ok": True,
        "numero": proc.get("llaveProceso") or numero,
        "id_proceso": id_proceso,
        "fecha_radicacion": _fmt_date(proc.get("fechaProceso")),
        "ultima_actuacion": ultima,
        "despacho": (proc.get("despacho") or "").strip(),
        "departamento": (proc.get("departamento") or "").strip(),
        "sujetos_procesales": (proc.get("sujetosProcesales") or "").replace("\r\n", "\n").strip(),
        "traza": traza[:25],
        "url_oficial": cpnu_proceso_url(id_proceso),
        "consultado_en": datetime.now(timezone.utc).isoformat(),
    }
