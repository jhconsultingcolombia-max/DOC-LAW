"""URL pública de la app (correo, pixel de apertura, enlaces externos)."""
import os


def public_site_origin() -> str:
    """Origen https sin prefijo /doc-law (ej. Azure App Service)."""
    base = (os.environ.get("LEGAL_PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if base:
        return base
    host = (os.environ.get("WEBSITE_HOSTNAME") or "").strip()
    if host:
        if host.startswith("localhost") or host.startswith("127.0.0.1"):
            return f"http://{host}"
        return f"https://{host}"
    return ""


def public_app_base() -> str:
    """Base con LEGAL_URL_PREFIX (ej. https://....azurewebsites.net/doc-law)."""
    origin = public_site_origin()
    prefix = (os.environ.get("LEGAL_URL_PREFIX") or "").rstrip("/")
    if origin:
        return f"{origin}{prefix}"
    return prefix


def pixel_base_is_local() -> bool:
    explicit = (os.environ.get("LEGAL_PUBLIC_BASE_URL") or "").strip().lower()
    if explicit:
        return any(x in explicit for x in ("127.0.0.1", "localhost", "0.0.0.0"))
    if (os.environ.get("WEBSITE_HOSTNAME") or "").strip():
        return False
    return True


