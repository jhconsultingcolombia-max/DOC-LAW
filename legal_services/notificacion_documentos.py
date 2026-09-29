"""Genera y archiva documentos de notificación (local + Google Drive)."""
from __future__ import annotations

import logging
from pathlib import Path

from legal_services.google_drive_storage import upload_file as drive_upload
from legal_services.notificacion_citacion_docx import generate_citacion_docx
from legal_services.notificacion_juzgado_docx import default_juzgado_campos, generate_juzgado_docx
from legal_services.notificacion_service import _notif_dir, get_notificacion, update_notificacion
from legal_services.notificacion_template import parse_campos_from_cuerpo

log = logging.getLogger(__name__)


def _ensure_campos_juzgado(record: dict) -> dict:
    if record.get("campos_juzgado"):
        return record["campos_juzgado"]
    parsed = record.get("campos_parseados") or parse_campos_from_cuerpo(record.get("cuerpo") or "")
    return default_juzgado_campos(parsed)


def _save_drive(tenant_id: str, case_id: str, notif_id: str, kind: str, fname: str, dest: Path) -> None:
    try:
        meta = drive_upload(f"{tenant_id}/{case_id}", fname, dest.read_bytes())
        if meta:
            update_notificacion(
                tenant_id,
                case_id,
                notif_id,
                {"archivos_drive": {kind: meta}, "archivos_onedrive": {kind: meta}},
            )
    except Exception as exc:
        log.warning("No se pudo subir a Google Drive (%s): %s", kind, exc)


def local_doc_path(tenant_id: str, case_id: str, notif_id: str, kind: str) -> Path:
    return _notif_dir(tenant_id, case_id) / f"{kind}_{notif_id}.docx"


def generate_juzgado(
    tenant_id: str, case_id: str, notif_id: str, *, sync_drive: bool = True
) -> tuple[Path, dict]:
    record = get_notificacion(tenant_id, case_id, notif_id)
    if not record:
        raise ValueError("Notificación no encontrada.")
    campos = _ensure_campos_juzgado(record)
    dest = local_doc_path(tenant_id, case_id, notif_id, "juzgado")
    generate_juzgado_docx(campos, dest)
    if sync_drive:
        _save_drive(tenant_id, case_id, notif_id, "juzgado", f"Constancia_juzgado_{notif_id}.docx", dest)
    return dest, campos


def generate_citacion(
    tenant_id: str, case_id: str, notif_id: str, *, sync_drive: bool = True
) -> Path:
    record = get_notificacion(tenant_id, case_id, notif_id)
    if not record:
        raise ValueError("Notificación no encontrada.")
    dest = local_doc_path(tenant_id, case_id, notif_id, "citacion")
    generate_citacion_docx(record, dest)
    if sync_drive:
        _save_drive(tenant_id, case_id, notif_id, "citacion", f"Citacion_{notif_id}.docx", dest)
    return dest
