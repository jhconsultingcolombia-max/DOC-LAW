"""Plantilla de notificación electrónica (formato citación judicial)."""
from __future__ import annotations

import html
import re
from datetime import datetime, timedelta, timezone

CO_TZ = timezone(timedelta(hours=-5))

PH = {
    "juzgado_nombre": "Ingresar nombre del juzgado",
    "juzgado_direccion": "Ingresar dirección del juzgado",
    "juzgado_correo": "Ingresar correo del juzgado",
    "fecha_notificacion": "Ingresar fecha (dd/mm/aaaa)",
    "destinatario_nombre": "Ingresar nombre del destinatario",
    "radicado": "Ingresar radicado del proceso",
    "naturaleza_proceso": "Ingresar naturaleza del proceso",
    "fecha_providencia": "Ingresar fecha de la providencia",
    "demandante": "Ingresar nombre del demandante",
    "demandado": "Ingresar nombre del demandado",
    "link_demanda": "Ingresar enlace a la demanda (opcional)",
    "link_mandamiento": "Ingresar enlace al mandamiento de pago (opcional)",
    "firmante_nombre": "Ingresar nombre quien firma",
    "firmante_cargo": "Ingresar cargo",
    "firmante_empresa": "Ingresar empresa / despacho",
    "firmante_celular": "Ingresar celular",
    "firmante_direccion": "Ingresar dirección oficina",
}


def _today_co() -> str:
    return datetime.now(CO_TZ).strftime("%d/%m/%Y")


def default_fields(caso: dict | None = None) -> dict:
    caso = caso or {}
    partes = caso.get("partes") or []
    demandado = next((p.get("nombre") for p in partes if (p.get("tipo") or "").lower() == "demandado"), "")
    demandante = next((p.get("nombre") for p in partes if (p.get("tipo") or "").lower() == "demandante"), "")
    radicado_raw = (caso.get("procesos_radicados") or "").strip()
    radicado = radicado_raw.split()[0] if radicado_raw and radicado_raw.lower() != "no hay" else PH["radicado"]

    return {
        "saludo_intro": "Buenos días, se notifica demanda de la referencia.",
        "link_demanda": PH["link_demanda"],
        "link_mandamiento": PH["link_mandamiento"],
        "juzgado_nombre": PH["juzgado_nombre"],
        "juzgado_direccion": PH["juzgado_direccion"],
        "juzgado_correo": PH["juzgado_correo"],
        "fecha_notificacion": _today_co(),
        "destinatario_nombre": demandado or caso.get("cliente_nombre") or PH["destinatario_nombre"],
        "radicado": radicado,
        "naturaleza_proceso": caso.get("rama_nombre") or PH["naturaleza_proceso"],
        "fecha_providencia": PH["fecha_providencia"],
        "demandante": demandante or PH["demandante"],
        "demandado": demandado or PH["demandado"],
        "anexos_linea": (
            "Anexos: Copia de demanda y anexos (_X_) Auto admisorio (__) y/o "
            "Mandamiento de Pago (_X_) que se notifica."
        ),
        "firmante_nombre": PH["firmante_nombre"],
        "firmante_cargo": PH["firmante_cargo"],
        "firmante_empresa": PH["firmante_empresa"],
        "firmante_celular": PH["firmante_celular"],
        "firmante_direccion": PH["firmante_direccion"],
    }


def default_asunto(fields: dict) -> str:
    rad = (fields.get("radicado") or "").strip()
    if rad.startswith("Ingresar"):
        rad = "[RADICADO]"
    return f"NOTIFICACIÓN ELECTRÓNICA - RADICADO {rad}."


def _e(text: str) -> str:
    return html.escape((text or "").strip())


def _link_line(label: str, url: str) -> str:
    u = (url or "").strip()
    if not u or u.startswith("Ingresar"):
        return ""
    safe = _e(u)
    if u.startswith("http://") or u.startswith("https://"):
        return f'<p style="margin:8px 0;"><strong>{_e(label)}:</strong> <a href="{safe}">{safe}</a></p>'
    return f'<p style="margin:8px 0;"><strong>{_e(label)}:</strong> {_e(u)}</p>'


def build_plain_body(fields: dict, destinatario_email: str) -> str:
    f = {**default_fields(), **(fields or {})}
    lines = [
        f.get("saludo_intro") or "",
        "",
        f"República de Colombia",
        f"Rama Judicial del Poder Público",
        f"Consejo Superior de la Judicatura",
        f.get("juzgado_nombre") or "",
        f.get("juzgado_direccion") or "",
        f.get("juzgado_correo") or "",
        "",
        "NOTIFICACIÓN PERSONAL",
        f"FECHA: {f.get('fecha_notificacion') or ''}",
        "SEÑOR(A)",
        f"Nombre: {f.get('destinatario_nombre') or ''}",
        f"Dirección: {destinatario_email or ''}",
        "",
        f"RADICADO: {f.get('radicado') or ''}",
        f"NATURALEZA: {f.get('naturaleza_proceso') or ''}",
        f"FECHA PROVIDENCIA: {f.get('fecha_providencia') or ''}",
        f"DEMANDANTE: {f.get('demandante') or ''}",
        f"DEMANDADO: {f.get('demandado') or ''}",
        "",
        (
            "La notificación personal se entenderá realizada una vez transcurridos dos días hábiles "
            "siguientes al envío del mensaje y los términos empezarán a correr a partir del día siguiente al "
            "de la notificación. El demandado cuenta con 10 días para contestar la demanda, lo cual deberá "
            "hacer por medio del correo electrónico indicado en el encabezado de la presente citación."
        ),
        "",
        f.get("anexos_linea") or "",
        "",
        "Cordialmente,",
        f.get("firmante_nombre") or "",
        f.get("firmante_cargo") or "",
        f.get("firmante_empresa") or "",
        f.get("firmante_celular") or "",
        f.get("firmante_direccion") or "",
    ]
    if f.get("link_demanda") and not str(f["link_demanda"]).startswith("Ingresar"):
        lines.insert(2, f"Link demanda: {f['link_demanda']}")
    if f.get("link_mandamiento") and not str(f["link_mandamiento"]).startswith("Ingresar"):
        lines.insert(3, f"Link mandamiento de pago: {f['link_mandamiento']}")
    return "\n".join(lines).strip()


def build_html_email(fields: dict, destinatario_email: str, pixel_url: str) -> str:
    f = {**default_fields(), **(fields or {})}
    px = _e(pixel_url)
    intro = _e(f.get("saludo_intro") or "")
    legal = (
        "La notificación personal se entenderá realizada una vez transcurridos dos días hábiles "
        "siguientes al envío del mensaje y los términos empezarán a correr a partir del día siguiente al "
        "de la notificación. El demandado cuenta con 10 días para contestar la demanda, lo cual deberá "
        "hacer por medio del correo electrónico indicado en el encabezado de la presente citación."
    )

    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/></head>
<body style="margin:0;padding:0;background:#f4f4f4;font-family:'Segoe UI',Arial,sans-serif;color:#1a1a1a;">
<img src="{px}" width="600" height="8" alt="" style="display:block;width:100%;max-width:600px;height:8px;border:0;margin:0 auto;" />
<table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="max-width:640px;margin:0 auto;background:#ffffff;">
<tr><td style="padding:24px 28px;">
<p style="margin:0 0 16px;font-size:15px;line-height:1.5;">{intro}</p>
{_link_line("Link demanda", f.get("link_demanda") or "")}
{_link_line("Link mandamiento de pago", f.get("link_mandamiento") or "")}
<div style="text-align:center;margin:20px 0 16px;font-size:13px;line-height:1.45;color:#333;">
<p style="margin:4px 0;">República de Colombia</p>
<p style="margin:4px 0;">Rama Judicial del Poder Público</p>
<p style="margin:4px 0;">Consejo Superior de la Judicatura</p>
<p style="margin:12px 0 4px;font-weight:700;font-size:14px;">{_e(f.get("juzgado_nombre") or "")}</p>
<p style="margin:4px 0;">{_e(f.get("juzgado_direccion") or "")}</p>
<p style="margin:4px 0;">{_e(f.get("juzgado_correo") or "")}</p>
</div>
<p style="margin:16px 0 8px;font-weight:700;text-align:center;">NOTIFICACIÓN PERSONAL</p>
<p style="margin:8px 0;"><strong>FECHA:</strong> {_e(f.get("fecha_notificacion") or "")}</p>
<p style="margin:8px 0;"><strong>SEÑOR(A)</strong></p>
<p style="margin:4px 0;"><strong>Nombre:</strong> {_e(f.get("destinatario_nombre") or "")}</p>
<p style="margin:4px 0 16px;"><strong>Dirección:</strong> {_e(destinatario_email)}</p>
<table role="presentation" width="100%" cellpadding="6" cellspacing="0" style="border-collapse:collapse;font-size:13px;margin:12px 0;">
<tr style="background:#eef1f5;">
<th align="left" style="border:1px solid #ccc;">RADICADO DEL PROCESO</th>
<th align="left" style="border:1px solid #ccc;">NATURALEZA DEL PROCESO</th>
<th align="left" style="border:1px solid #ccc;">FECHA DE LA PROVIDENCIA</th>
</tr>
<tr>
<td style="border:1px solid #ccc;">{_e(f.get("radicado") or "")}</td>
<td style="border:1px solid #ccc;">{_e(f.get("naturaleza_proceso") or "")}</td>
<td style="border:1px solid #ccc;">{_e(f.get("fecha_providencia") or "")}</td>
</tr>
<tr style="background:#eef1f5;">
<th align="left" style="border:1px solid #ccc;">DEMANDANTE</th>
<th align="left" colspan="2" style="border:1px solid #ccc;">DEMANDADO</th>
</tr>
<tr>
<td style="border:1px solid #ccc;vertical-align:top;">{_e(f.get("demandante") or "")}</td>
<td colspan="2" style="border:1px solid #ccc;vertical-align:top;">{_e(f.get("demandado") or "")}</td>
</tr>
</table>
<p style="margin:16px 0;font-size:13px;line-height:1.55;text-align:justify;">{_e(legal)}</p>
<p style="margin:16px 0;font-size:13px;line-height:1.5;">{_e(f.get("anexos_linea") or "")}</p>
<p style="margin:20px 0 4px;">Cordialmente,</p>
<p style="margin:4px 0;">{_e(f.get("firmante_nombre") or "")}</p>
<p style="margin:4px 0;">{_e(f.get("firmante_cargo") or "")}</p>
<p style="margin:4px 0;">{_e(f.get("firmante_empresa") or "")}</p>
<p style="margin:4px 0;">{_e(f.get("firmante_celular") or "")}</p>
<p style="margin:4px 0 8px;">{_e(f.get("firmante_direccion") or "")}</p>
<img src="{px}" width="600" height="8" alt="" style="display:block;width:100%;max-width:600px;height:8px;border:0;" />
</td></tr>
</table>
</body>
</html>"""


def default_mensaje(caso: dict | None = None) -> str:
    return build_plain_body(default_fields(caso), "Ingresar correo del destinatario")


def build_html_from_mensaje(cuerpo: str, pixel_url: str) -> str:
    """HTML del correo a partir del texto editado en pantalla."""
    px = _e(pixel_url)
    body = _e(cuerpo or "").replace("\n", "<br/>\n")
    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"/></head>
<body style="margin:0;padding:0;background:#f4f4f4;font-family:'Segoe UI',Arial,sans-serif;color:#1a1a1a;">
<img src="{px}" width="600" height="8" alt="" style="display:block;width:100%;max-width:640px;height:8px;border:0;margin:0 auto;" />
<table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="max-width:640px;margin:0 auto;background:#ffffff;">
<tr><td style="padding:24px 28px;font-size:14px;line-height:1.55;">
<div style="line-height:1.55;">{body}</div>
<img src="{px}" width="600" height="8" alt="" style="display:block;width:100%;max-width:640px;height:8px;border:0;margin-top:16px;" />
</td></tr>
</table>
</body>
</html>"""


def merge_fields(raw: dict | None) -> dict:
    base = default_fields()
    if not raw:
        return base
    for k, v in raw.items():
        if k in base and v is not None:
            base[k] = str(v).strip()
    return base


def parse_campos_from_cuerpo(cuerpo: str) -> dict:
    """Extrae campos editables del mensaje enviado (plantilla de citación)."""
    lines = [ln.strip() for ln in (cuerpo or "").replace("\r\n", "\n").split("\n")]
    out: dict[str, str] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.lower().startswith("nombre:"):
            out["destinatario_nombre"] = line.split(":", 1)[1].strip()
        if line.lower().startswith("dirección:") or line.lower().startswith("direccion:"):
            out["destinatario_email"] = line.split(":", 1)[1].strip()
        if line.upper().startswith("RADICADO:"):
            out["radicado"] = line.split(":", 1)[1].strip()
        if line.upper().startswith("DEMANDANTE:"):
            out["demandante"] = line.split(":", 1)[1].strip()
        if line.upper().startswith("DEMANDADO:"):
            out["demandado"] = line.split(":", 1)[1].strip()
        if "república de colombia" in line.lower():
            juz_lines = []
            for j in range(i + 3, min(i + 6, len(lines))):
                if lines[j] and not lines[j].upper().startswith("NOTIFICACIÓN"):
                    juz_lines.append(lines[j])
                else:
                    break
            if juz_lines:
                out["juzgado_nombre"] = juz_lines[0]
                if len(juz_lines) > 1:
                    out["juzgado_direccion"] = juz_lines[1]
                if len(juz_lines) > 2:
                    out["juzgado_correo"] = juz_lines[2]
        i += 1
    block = " ".join(lines)
    m = re.search(r"\b(050014\d{15,})\b", block)
    if m and "radicado" not in out:
        out["radicado"] = m.group(1)
    return out
