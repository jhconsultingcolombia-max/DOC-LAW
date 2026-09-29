"""Caché Markdown (.ia.md) al subir archivos — menos tokens y menos tiempo en cada análisis."""
from datetime import datetime, timezone
from pathlib import Path

from legal_services.document_reader import MAX_CHARS_PER_FILE, prepare_legal_document_text, read_file_text

IA_MD_SUFFIX = ".ia.md"
_CONVERTIBLE = {".pdf", ".docx", ".doc", ".txt", ".md", ".csv"}


def sidecar_path(source: Path) -> Path:
    return source.with_name(source.name + IA_MD_SUFFIX)


def _strip_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text.strip()
    end = text.find("\n---\n", 3)
    if end < 0:
        return text.strip()
    return text[end + 5 :].strip()


def build_ia_markdown(source: Path, context: str = "") -> Path | None:
    """Extrae texto, lo prepara para IA y guarda sidecar .ia.md junto al original."""
    if not source.is_file() or source.suffix.lower() not in _CONVERTIBLE:
        return None
    if source.name.endswith(IA_MD_SUFFIX):
        return None

    raw = read_file_text(source)
    if not raw.strip():
        return None

    prepared = prepare_legal_document_text(raw, MAX_CHARS_PER_FILE, context)
    dest = sidecar_path(source)
    header = (
        "---\n"
        f"source: {source.name}\n"
        f"generated: {datetime.now(timezone.utc).isoformat()}\n"
        f"original_chars: {len(raw)}\n"
        f"ia_chars: {len(prepared)}\n"
        "---\n\n"
    )
    dest.write_text(header + prepared, encoding="utf-8")
    return dest


def load_text_for_ia(source: Path, context: str = "") -> tuple[str, int, str]:
    """
    Devuelve (texto_para_ia, caracteres_originales, origen).
    origen: 'cache' | 'fresh'
    """
    side = sidecar_path(source)
    if side.is_file() and side.stat().st_mtime >= source.stat().st_mtime:
        cached = _strip_frontmatter(side.read_text(encoding="utf-8"))
        orig_chars = 0
        try:
            for line in side.read_text(encoding="utf-8").splitlines():
                if line.startswith("original_chars:"):
                    orig_chars = int(line.split(":", 1)[1].strip())
                    break
        except (ValueError, OSError):
            orig_chars = len(read_file_text(source))
        return cached, orig_chars, "cache"

    raw = read_file_text(source)
    prepared = prepare_legal_document_text(raw, MAX_CHARS_PER_FILE, context)
    build_ia_markdown(source, context)
    return prepared, len(raw), "fresh"


def is_sidecar(path: Path) -> bool:
    return path.name.endswith(IA_MD_SUFFIX)
