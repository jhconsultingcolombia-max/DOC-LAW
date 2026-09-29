import html
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from legal_services.case_service import case_dir, get_case
from legal_services.env_paths import environment_data_root
from legal_services.mail_service import mail_configured, send_html_email
from legal_services.notificacion_juzgado_docx import default_juzgado_campos
from legal_services.notificacion_template import (
    build_html_email,
    build_html_from_mensaje,
    build_plain_body,
    default_asunto,
    merge_fields,
    parse_campos_from_cuerpo,
)
from legal_services.public_url import public_app_base
from legal_services.tenant_storage import _safe_name, tenant_root

MAX_ADJUNTO_BYTES = 20 * 1024 * 1024

# 1×1 PNG transparente
TRACKING_PIXEL = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _notif_dir(tenant_id: str, case_id: str) -> Path:
    path = case_dir(tenant_id, case_id) / "notificaciones"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _track_index_path(token: str) -> Path:
    root = environment_data_root() / "track_index"
    root.mkdir(parents=True, exist_ok=True)
    safe = _safe_name(token)[:120]
    return root / f"{safe}.json"


def tracking_pixel_url(token: str, request_root: str | None = None) -> str:
    prefix = (os.environ.get("LEGAL_URL_PREFIX") or "").rstrip("/")
    path = f"{prefix}/track/n/{token}.png"

    tunnel = (os.environ.get("LEGAL_PUBLIC_TUNNEL_URL") or "").strip().rstrip("/")
    if tunnel:
        return f"{tunnel}{path}"

    pub = public_app_base()
    if pub:
        return f"{pub.rstrip('/')}/track/n/{token}.png"

    if request_root:
        root = request_root.rstrip("/")
        if root.endswith(prefix) and prefix:
            return f"{root}/track/n/{token}.png"
        return f"{root}{path}"
    return path


def update_notificacion(tenant_id: str, case_id: str, notif_id: str, patch: dict) -> dict | None:
    record = get_notificacion(tenant_id, case_id, notif_id)
    if not record:
        return None
    if "campos_juzgado" in patch and isinstance(patch["campos_juzgado"], dict):
        base = record.get("campos_juzgado") or default_juzgado_campos(
            record.get("campos_parseados") or parse_campos_from_cuerpo(record.get("cuerpo") or "")
        )
        base.update({k: str(v).strip() for k, v in patch["campos_juzgado"].items() if v is not None})
        record["campos_juzgado"] = base
    if "archivos_onedrive" in patch:
        record["archivos_onedrive"] = {**(record.get("archivos_onedrive") or {}), **patch["archivos_onedrive"]}
    if "archivos_drive" in patch:
        record["archivos_drive"] = {**(record.get("archivos_drive") or {}), **patch["archivos_drive"]}
    return _save_notificacion(tenant_id, case_id, record)


def get_notificacion(tenant_id: str, case_id: str, notif_id: str) -> dict | None:
    path = _notif_dir(tenant_id, case_id) / f"{_safe_name(notif_id)}.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def list_notificaciones(tenant_id: str, case_id: str) -> list[dict]:
    folder = _notif_dir(tenant_id, case_id)
    items = []
    for path in folder.glob("*.json"):
        try:
            items.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return sorted(items, key=lambda x: x.get("enviado_en") or x.get("creado") or "", reverse=True)


def _save_notificacion(tenant_id: str, case_id: str, record: dict) -> dict:
    folder = _notif_dir(tenant_id, case_id)
    path = folder / f"{_safe_name(record['id'])}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def _norm_rel_path(rel: str) -> str:
    return (rel or "").replace("\\", "/").lstrip("/")


def _tenant_file(tenant_id: str, rel_path: str) -> Path | None:
    root = tenant_root(tenant_id).resolve()
    rel = _norm_rel_path(rel_path)
    if not rel or ".." in rel.split("/"):
        return None
    path = (root / rel).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None
    if not path.is_file():
        return None
    return path


def _case_allows_document_path(tenant_id: str, case_id: str, rel_path: str) -> bool:
    rel = _norm_rel_path(rel_path)
    caso = get_case(tenant_id, case_id)
    if not caso:
        return False
    for doc in caso.get("documentos") or []:
        if _norm_rel_path(doc.get("path") or "") == rel:
            return True
    prefix = f"casos/{_safe_name(case_id)}/documentos/"
    return rel.startswith(prefix)


def _read_adjunto(
    tenant_id: str,
    case_id: str,
    *,
    documento_path: str | None = None,
    upload_name: str | None = None,
    upload_data: bytes | None = None,
) -> tuple[str, bytes] | None:
    if documento_path:
        rel = _norm_rel_path(documento_path)
        if not _case_allows_document_path(tenant_id, case_id, rel):
            raise ValueError("Documento no permitido o no pertenece a este caso.")
        path = _tenant_file(tenant_id, rel)
        if not path:
            raise ValueError("No se encontró el archivo del caso.")
        data = path.read_bytes()
        if len(data) > MAX_ADJUNTO_BYTES:
            raise ValueError("El documento supera el límite de 20 MB.")
        return path.name, data

    if upload_data:
        if not upload_name:
            raise ValueError("Nombre de archivo inválido.")
        if len(upload_data) > MAX_ADJUNTO_BYTES:
            raise ValueError("El adjunto supera el límite de 20 MB.")
        safe_name = Path(upload_name).name
        if not safe_name or safe_name in (".", ".."):
            raise ValueError("Nombre de archivo inválido.")
        return safe_name, upload_data

    return None


def _store_adjunto_copy(tenant_id: str, case_id: str, notif_id: str, filename: str, data: bytes) -> str:
    folder = _notif_dir(tenant_id, case_id) / "adjuntos"
    folder.mkdir(parents=True, exist_ok=True)
    safe = _safe_name(f"{notif_id}_{Path(filename).name}")[:180]
    path = folder / safe
    path.write_bytes(data)
    rel = path.relative_to(tenant_root(tenant_id)).as_posix()
    return rel


def _wrap_html_plain(cuerpo: str, pixel_url: str) -> str:
    body = html.escape(cuerpo).replace("\n", "<br/>\n")
    pixel = html.escape(pixel_url, quote=True)
    return f"""<!DOCTYPE html>
<html lang="es"><body style="font-family:Segoe UI,Arial,sans-serif;font-size:15px;color:#222;">
<img src="{pixel}" width="600" height="8" alt="" style="display:block;width:100%;max-width:600px;height:8px;border:0;" />
<div>{body}</div>
<img src="{pixel}" width="600" height="8" alt="" style="display:block;width:100%;max-width:600px;height:8px;border:0;" />
</body></html>"""


def create_and_send(
    tenant_id: str,
    case_id: str,
    para: str,
    asunto: str,
    cuerpo: str,
    remitente_usuario: str,
    request_root: str | None = None,
    documento_path: str | None = None,
    upload_name: str | None = None,
    upload_data: bytes | None = None,
    plantilla_campos: dict | None = None,
) -> dict:
    if get_case(tenant_id, case_id) is None:
        raise ValueError("Caso no encontrado.")

    para = (para or "").strip()
    asunto = (asunto or "").strip()
    fields = merge_fields(plantilla_campos) if plantilla_campos is not None else None

    if not para or "@" not in para:
        raise ValueError("Indique un correo válido en «Para».")
    if fields is not None:
        if not asunto:
            asunto = default_asunto(fields)
        cuerpo = build_plain_body(fields, para)
    else:
        cuerpo = (cuerpo or "").strip()
        if not asunto:
            raise ValueError("Indique el asunto.")
        if not cuerpo:
            raise ValueError("Indique el mensaje.")

    notif_id = uuid.uuid4().hex[:12]
    token = uuid.uuid4().hex
    pixel_url = tracking_pixel_url(token, request_root=request_root)
    dry = (os.environ.get("MAIL_DRY_RUN") or "").strip().lower() in ("1", "true", "yes")

    record = {
        "id": notif_id,
        "case_id": case_id,
        "para": para,
        "asunto": asunto,
        "cuerpo": cuerpo,
        "plantilla_campos": fields,
        "formato": "plantilla_judicial" if fields is not None else "texto",
        "campos_parseados": parse_campos_from_cuerpo(cuerpo),
        "campos_juzgado": default_juzgado_campos(parse_campos_from_cuerpo(cuerpo)),
        "archivos_onedrive": {},
        "archivos_drive": {},
        "token": token,
        "track_url": pixel_url,
        "remitente": remitente_usuario,
        "creado": datetime.now(timezone.utc).isoformat(),
        "enviado_en": None,
        "estado": "pendiente",
        "error_envio": None,
        "abierto_en": None,
        "abierto_ip": None,
        "abierto_user_agent": None,
        "modo_envio": "dry_run" if dry else "smtp",
        "adjuntos": [],
    }

    if documento_path and upload_data:
        raise ValueError("Elija un documento del caso o suba un archivo, no ambos a la vez.")

    adjunto = _read_adjunto(
        tenant_id,
        case_id,
        documento_path=documento_path,
        upload_name=upload_name,
        upload_data=upload_data,
    )

    mail_attachments: list[tuple[str, bytes, str | None]] = []
    if adjunto:
        fname, fdata = adjunto
        stored_rel = _store_adjunto_copy(tenant_id, case_id, notif_id, fname, fdata)
        origen = "caso" if documento_path else "upload"
        record["adjuntos"] = [
            {
                "nombre": fname,
                "path": stored_rel,
                "origen": origen,
                "documento_caso": _norm_rel_path(documento_path) if documento_path else None,
            }
        ]
        mail_attachments.append((fname, fdata, None))

    if fields is not None:
        html_body = build_html_email(fields, para, pixel_url)
    else:
        html_body = build_html_from_mensaje(cuerpo, pixel_url)
    text_body = cuerpo
    if record["adjuntos"]:
        names = ", ".join(a["nombre"] for a in record["adjuntos"])
        text_body += f"\n\nAdjunto: {names}"

    try:
        if not mail_configured():
            raise ValueError(
                "Correo no configurado. Use MAIL_DRY_RUN=1 para prueba local o configure SMTP_* en .env."
            )
        send_html_email(para, asunto, html_body, text_body=text_body, attachments=mail_attachments or None)
        record["estado"] = "enviado"
        record["enviado_en"] = datetime.now(timezone.utc).isoformat()
    except Exception as exc:
        record["estado"] = "error"
        record["error_envio"] = str(exc)
        _save_notificacion(tenant_id, case_id, record)
        raise

    _track_index_path(token).write_text(
        json.dumps({"tenant_id": tenant_id, "case_id": case_id, "notification_id": notif_id}),
        encoding="utf-8",
    )
    return _save_notificacion(tenant_id, case_id, record)


def record_open(token: str, ip: str | None, user_agent: str | None) -> bool:
    idx = _track_index_path(token)
    if not idx.is_file():
        return False
    try:
        meta = json.loads(idx.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False

    tenant_id = meta.get("tenant_id")
    case_id = meta.get("case_id")
    notif_id = meta.get("notification_id")
    if not tenant_id or not case_id or not notif_id:
        return False

    path = _notif_dir(tenant_id, case_id) / f"{_safe_name(notif_id)}.json"
    if not path.is_file():
        return False
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False

    if not record.get("abierto_en"):
        record["abierto_en"] = datetime.now(timezone.utc).isoformat()
        record["abierto_ip"] = ip
        record["abierto_user_agent"] = (user_agent or "")[:500]
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def tracking_pixel_bytes() -> bytes:
    return TRACKING_PIXEL
