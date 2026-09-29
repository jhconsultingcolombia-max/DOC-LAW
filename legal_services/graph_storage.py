"""Subida de documentos a SharePoint / OneDrive (Microsoft Graph)."""
from __future__ import annotations

import logging
import os
from pathlib import PurePosixPath

import requests

log = logging.getLogger(__name__)

GRAPH = "https://graph.microsoft.com/v1.0"


def _settings_ok() -> bool:
    return all(
        os.environ.get(k)
        for k in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET")
    )


def _token() -> str:
    import msal

    app = msal.ConfidentialClientApplication(
        os.environ["AZURE_CLIENT_ID"],
        authority=f"https://login.microsoftonline.com/{os.environ['AZURE_TENANT_ID']}",
        client_credential=os.environ["AZURE_CLIENT_SECRET"],
    )
    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    if "access_token" not in result:
        raise RuntimeError(result.get("error_description") or "No se pudo autenticar con Graph.")
    return result["access_token"]


def _site_id(token: str) -> str:
    host = os.environ.get("ONEDRIVE_SITE_HOST") or os.environ.get("SHAREPOINT_HOST", "")
    site_path = os.environ.get("ONEDRIVE_SITE_PATH") or os.environ.get(
        "SHAREPOINT_SITE_PATH", "/sites/DOC_LAW"
    )
    if not host:
        raise RuntimeError("Configure ONEDRIVE_SITE_HOST (ej. jhconsulting.sharepoint.com).")
    url = f"{GRAPH}/sites/{host}:{site_path}"
    res = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=60)
    res.raise_for_status()
    return res.json()["id"]


def upload_file(relative_folder: str, filename: str, data: bytes) -> dict | None:
    """
    Sube archivo a la biblioteca del sitio. Devuelve {webUrl, id, path} o None si Graph no está configurado.
    """
    if not _settings_ok():
        log.info("Graph no configurado; documento solo en disco local.")
        return None

    token = _token()
    site_id = _site_id(token)
    base = (os.environ.get("ONEDRIVE_NOTIF_FOLDER") or "DOC_LAW/Notificaciones").strip("/")
    folder = str(PurePosixPath(base) / relative_folder.strip("/"))
    encoded = requests.utils.quote(f"{folder}/{filename}")
    url = f"{GRAPH}/sites/{site_id}/drive/root:/{encoded}:/content"
    res = requests.put(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        },
        data=data,
        timeout=120,
    )
    if res.status_code not in (200, 201):
        log.error("Error subiendo a OneDrive: %s %s", res.status_code, res.text[:300])
        raise RuntimeError("No se pudo guardar el documento en OneDrive.")
    meta = res.json()
    return {
        "id": meta.get("id"),
        "webUrl": meta.get("webUrl"),
        "path": f"{folder}/{filename}",
    }
