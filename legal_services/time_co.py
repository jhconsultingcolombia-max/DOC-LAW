"""Fechas/horas en zona Colombia (UTC−5)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

CO_OFFSET = timedelta(hours=-5)


def parse_iso(iso: str) -> datetime | None:
    if not iso or not isinstance(iso, str):
        return None
    text = iso.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def format_iso_colombia(iso: str | None, *, with_seconds: bool = False) -> str:
    if not iso:
        return "—"
    dt = parse_iso(iso)
    if not dt:
        return "—"
    utc = dt.astimezone(timezone.utc).replace(tzinfo=None)
    co = utc + CO_OFFSET
    fmt = "%d/%m/%Y %H:%M:%S" if with_seconds else "%d/%m/%Y %H:%M"
    return co.strftime(fmt)


def now_colombia_str(*, with_seconds: bool = False) -> str:
    utc = datetime.now(timezone.utc).replace(tzinfo=None)
    co = utc + CO_OFFSET
    fmt = "%d/%m/%Y %H:%M:%S" if with_seconds else "%d/%m/%Y %H:%M"
    return co.strftime(fmt)


def enrich_notificacion_display(record: dict) -> dict:
    """Campos de solo lectura para la UI (no persistir en JSON del caso)."""
    out = dict(record)
    sent = record.get("enviado_en") or record.get("creado")
    out["enviado_co"] = format_iso_colombia(sent) if sent else None
    abierto = record.get("abierto_en")
    out["abierto_co"] = format_iso_colombia(abierto) if abierto else None
    return out
