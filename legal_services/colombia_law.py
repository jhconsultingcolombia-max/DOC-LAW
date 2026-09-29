"""Referencias y análisis preliminar — integración futura con SUIN-Juriscol / Azure OpenAI."""

CONSTITUCION_BASE = "https://www.constitucioncolombia.com/"

FUENTES_OFICIALES = {
    "constitucion": "https://www.constitucioncolombia.com/",
    "suin": "https://www.suin-juriscol.gov.co/",
    "congreso": "https://www.congresovisible.org/",
    "corte_constitucional": "https://www.corteconstitucional.gov.co/",
}


def preliminary_viability(rama: str, hechos: str, plazo_reportado: str | None) -> dict:
    hechos_lower = (hechos or "").lower()
    alertas = []
    if plazo_reportado:
        alertas.append(f"Verificar plazo reportado: {plazo_reportado}")
    if any(w in hechos_lower for w in ("prescripción", "caducidad", "venció", "vencio")):
        alertas.append("Urgente: evaluar prescripción/caducidad con abogado responsable.")
    return {
        "rama": rama,
        "viabilidad_preliminar": "requiere_revision" if alertas else "aparentemente_viable",
        "alertas": alertas,
        "documentos_sugeridos": "Ver checklist de la rama seleccionada",
    }


def build_legal_analysis(rama: str, hechos: str, partes: list[dict]) -> dict:
    """Borrador estructurado — en producción se enriquece con Azure OpenAI + SUIN."""
    a_favor = [
        "Identificar norma aplicable y hechos probables documentados.",
        "Verificar cumplimiento de requisitos procesales de la rama seleccionada.",
    ]
    en_contra = [
        "Evaluar prueba documental disponible vs. prueba requerida.",
        "Revisar posibles excepciones de la contraparte.",
    ]
    pasos = [
        "Completar checklist documental del cliente.",
        "Conciliación prejudicial (si aplica).",
        "Radicación o respuesta procesal según rol (demandante/demandado).",
        "Seguimiento de términos en agenda del despacho.",
    ]
    return {
        "fuentes_oficiales": FUENTES_OFICIALES,
        "marco_constitucional": "Revisar artículos aplicables en Constitución Política 1991.",
        "analisis_a_favor_cliente": a_favor,
        "analisis_en_contra": en_contra,
        "pasos_sugeridos": pasos,
        "disclaimer": "Borrador preliminar generado por JH consulting (DOC_LAW). Requiere revisión y firma del abogado.",
        "hechos_resumen": hechos[:500] if hechos else "",
        "partes_count": len(partes or []),
        "rama": rama,
    }


def draft_client_communication(caso: dict, analysis: dict) -> str:
    return f"""Estimado(a) cliente,

Hemos recibido su consulta en materia de {caso.get('rama_nombre', 'derecho')}.
Resumen preliminar: {caso.get('titulo', 'Su caso')}.

Próximos pasos sugeridos:
{chr(10).join('- ' + p for p in analysis.get('pasos_sugeridos', []))}

Este comunicado es informativo y no constituye opinión legal definitiva.

Atentamente,
{caso.get('abogado_responsable', 'Equipo jurídico JH consulting')}
"""
