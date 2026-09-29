import re

from pathlib import Path



MAX_CHARS_PER_FILE = 80000

MAX_TOTAL_CHARS = 120000



CHAPTER_SPLIT_RE = re.compile(

    r"(?=(?:CAP[ÍI]TULO|Capítulo|CAPITULO)\s+[IVXLCDM\d]+[\:\.]?)",

    re.IGNORECASE,

)



DISCIPLINARY_HINTS = (

    "XVIII", "XIX", "XXII", "XXIII", "XXIV",

    "DEBER", "PROHIBIC", "SANCI", "FALTA", "DISCIPLIN",

    "ALCOHOL", "EMBRIAG", "HORARIO", "ASISTENCIA", "TARDANZA",

)





def _read_txt(path: Path) -> str:

    for enc in ("utf-8", "latin-1", "cp1252"):

        try:

            return path.read_text(encoding=enc)

        except UnicodeDecodeError:

            continue

    return path.read_text(encoding="utf-8", errors="ignore")





def _read_pdf(path: Path) -> str:

    from pypdf import PdfReader



    reader = PdfReader(str(path))

    parts = []

    for page in reader.pages[:80]:

        parts.append(page.extract_text() or "")

    return "\n".join(parts)





def _iter_docx_blocks(document):

    from docx.oxml.table import CT_Tbl

    from docx.oxml.text.paragraph import CT_P

    from docx.table import Table

    from docx.text.paragraph import Paragraph



    for child in document.element.body.iterchildren():

        if isinstance(child, CT_P):

            yield Paragraph(child, document)

        elif isinstance(child, CT_Tbl):

            yield Table(child, document)





def _read_docx(path: Path) -> str:

    from docx import Document



    doc = Document(str(path))

    parts: list[str] = []

    for block in _iter_docx_blocks(doc):

        if hasattr(block, "rows"):

            for row in block.rows:

                cells = [c.text.strip() for c in row.cells if c.text.strip()]

                if cells:

                    parts.append(" | ".join(cells))

        else:

            text = (block.text or "").strip()

            if text:

                parts.append(text)

    return "\n".join(parts)





def read_file_text(path: Path) -> str:

    suffix = path.suffix.lower()

    if suffix in {".txt", ".md", ".csv"}:

        return _read_txt(path)

    if suffix == ".pdf":

        return _read_pdf(path)

    if suffix in {".docx", ".doc"}:

        if suffix == ".doc":

            return _read_txt(path)

        return _read_docx(path)

    return ""





def _has_article_text(text: str) -> bool:

    upper = text.upper()

    return "ARTÍCULO" in upper or "ARTICULO" in upper


def _extract_chapter_between(text: str, start_pat: str, end_pat: str) -> str:
    """Toma la última aparición del capítulo que incluye artículos (no solo índice)."""
    matches = list(re.finditer(start_pat, text, re.IGNORECASE))
    for match in reversed(matches):
        start = match.start()
        if not _has_article_text(text[start : start + 900]):
            continue
        end_match = re.search(end_pat, text[start + 20 :], re.IGNORECASE)
        end = start + 20 + end_match.start() if end_match else min(len(text), start + 18000)
        return text[start:end].strip()
    return ""


def _forced_disciplinary_sections(text: str) -> list[str]:
    pairs = [
        (r"CAP[ÍI]TULO\s+XVIII\b", r"CAP[ÍI]TULO\s+XIX\b"),
        (r"CAP[ÍI]TULO\s+XXII\b", r"CAP[ÍI]TULO\s+XXIII\b"),
        (r"CAP[ÍI]TULO\s+XXIII\b", r"CAP[ÍI]TULO\s+XXIV\b"),
        (r"CAP[ÍI]TULO\s+XXIV\b", r"CAP[ÍI]TULO\s+XXV\b"),
    ]
    sections = []
    for start_pat, end_pat in pairs:
        section = _extract_chapter_between(text, start_pat, end_pat)
        if section:
            sections.append(section)
    return sections


def prepare_legal_document_text(text: str, max_chars: int, context: str = "") -> str:

    """Incluye intro + capítulos relevantes cuando el reglamento es muy largo."""

    text = text.strip()

    if not text:

        return ""

    if len(text) <= max_chars:

        return text



    context_lower = (context or "").lower()

    intro = f"[INICIO DEL DOCUMENTO — definiciones y primeros artículos]\n{text[:9000]}"

    chunks: list[str] = [intro]

    used = len(intro)

    forced = _forced_disciplinary_sections(text)
    if forced:
        chunks.append("\n[CAPÍTULOS DISCIPLINARIOS COMPLETOS — XVIII, XXII, XXIII, XXIV]\n")
        used += len(chunks[-1])
        for section in forced:
            if used >= max_chars - 500:
                break
            budget = max_chars - used - 50
            piece = section if len(section) <= budget else section[:budget] + "\n[...continúa...]"
            chunks.append(piece)
            used += len(piece) + 2

    scored: list[tuple[int, int, str]] = []
    forced_text = "\n".join(forced)

    for part in CHAPTER_SPLIT_RE.split(text):

        part = part.strip()

        if len(part) < 100:

            continue

        if not _has_article_text(part) and len(part) < 800:

            continue

        upper = part.upper()

        score = 0

        for hint in DISCIPLINARY_HINTS:

            if hint in upper:

                score += 6

        for kw in ("alcohol", "embriag", "tard", "horario", "asist", "disciplin", "sancion", "falta"):

            if kw in part.lower():

                score += 4

            if kw in context_lower and kw in part.lower():

                score += 6

        if _has_article_text(part):

            score += 2

        if score > 0 and part not in forced_text:

            scored.append((score, len(part), part))



    scored.sort(key=lambda x: (-x[0], -x[1]))



    chunks.append("\n[CAPÍTULOS CON ARTÍCULOS — lectura completa para análisis]\n")

    used += len(chunks[-1])



    for score, _, part in scored:

        if used >= max_chars - 500:

            break

        budget = max_chars - used - 50

        if len(part) <= budget:

            chunks.append(part)

            used += len(part) + 2

        elif score >= 8 and budget > 1500:

            chunks.append(part[:budget] + "\n[...continúa en documento original...]")

            used += budget + 2



    if len(chunks) <= 2:

        third = max_chars // 3

        return (

            text[:third]

            + "\n\n[... SECCIÓN MEDIA ...]\n\n"

            + text[len(text) // 3 : len(text) // 3 + third]

            + "\n\n[... SECCIÓN FINAL ...]\n\n"

            + text[-third:]

        )[:max_chars]



    return "\n\n".join(chunks)[:max_chars]





def _prepare_text(raw: str, context: str = "") -> str:

    return prepare_legal_document_text(raw, MAX_CHARS_PER_FILE, context)





def collect_documents_from_files(paths: list[Path], context: str = "") -> list[dict]:

    items = []

    total = 0

    from legal_services.document_cache import is_sidecar, load_text_for_ia

    for path in paths:

        if not path.is_file() or is_sidecar(path):

            continue

        orig_chars = 0
        try:
            text, orig_chars, _src = load_text_for_ia(path, context)
        except Exception as exc:
            text = f"[Error leyendo archivo: {exc}]"

        if not text.strip():

            continue

        if total + len(text) > MAX_TOTAL_CHARS:

            text = text[: max(0, MAX_TOTAL_CHARS - total)]

        items.append({

            "nombre": path.name,

            "ruta": str(path),

            "contenido": text,

            "caracteres_originales": orig_chars,

        })

        total += len(text)

        if total >= MAX_TOTAL_CHARS:

            break

    return items





def collect_documents_from_dirs(dirs: list[Path], context: str = "") -> list[dict]:

    from legal_services.document_cache import is_sidecar, load_text_for_ia

    items = []

    total = 0

    exts = {".pdf", ".docx", ".doc", ".txt", ".md", ".csv"}

    for base in dirs:

        if not base.exists():

            continue

        for path in sorted(base.rglob("*")):

            if not path.is_file() or path.suffix.lower() not in exts or is_sidecar(path):

                continue

            orig_chars = 0
            try:

                text, orig_chars, _src = load_text_for_ia(path, context)

            except Exception as exc:

                text = f"[Error leyendo archivo: {exc}]"

            if not text.strip():

                continue

            if total + len(text) > MAX_TOTAL_CHARS:

                text = text[: max(0, MAX_TOTAL_CHARS - total)]

            items.append({

                "nombre": path.name,

                "ruta": str(path),

                "contenido": text,

                "caracteres_originales": orig_chars,

            })

            total += len(text)

            if total >= MAX_TOTAL_CHARS:

                return items

    return items


