"""Subida a Google Drive: OAuth (cuenta Gmail) o cuenta de servicio + carpeta compartida."""
from __future__ import annotations

import io
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

_FOLDER_CACHE: dict[str, str] = {}
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def _legal_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _credentials_path() -> Path | None:
    raw = (os.environ.get("GOOGLE_DRIVE_CREDENTIALS_JSON") or "").strip()
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = _legal_root() / raw
    return path if path.is_file() else None


def _oauth_configured() -> bool:
    cid = (os.environ.get("GOOGLE_DRIVE_CLIENT_ID") or "").strip()
    secret = (os.environ.get("GOOGLE_DRIVE_CLIENT_SECRET") or "").strip()
    refresh = (os.environ.get("GOOGLE_DRIVE_REFRESH_TOKEN") or "").strip()
    return bool(cid and secret and refresh)


def drive_configured() -> bool:
    root = (os.environ.get("GOOGLE_DRIVE_ROOT_FOLDER_ID") or "").strip()
    if not root:
        return False
    return _oauth_configured() or bool(_credentials_path())


def _drive_service():
    if not drive_configured():
        raise RuntimeError("Google Drive no configurado.")
    from googleapiclient.discovery import build

    if _oauth_configured():
        from google.oauth2.credentials import Credentials

        creds = Credentials(
            token=None,
            refresh_token=os.environ["GOOGLE_DRIVE_REFRESH_TOKEN"].strip(),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.environ["GOOGLE_DRIVE_CLIENT_ID"].strip(),
            client_secret=os.environ["GOOGLE_DRIVE_CLIENT_SECRET"].strip(),
            scopes=DRIVE_SCOPES,
        )
    else:
        from google.oauth2 import service_account

        creds = service_account.Credentials.from_service_account_file(
            str(_credentials_path()),
            scopes=DRIVE_SCOPES,
        )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _get_or_create_folder(service, parent_id: str, name: str) -> str:
    cache_key = f"{parent_id}/{name}"
    if cache_key in _FOLDER_CACHE:
        return _FOLDER_CACHE[cache_key]
    safe_name = name.replace("'", "\\'")
    query = (
        f"'{parent_id}' in parents and name = '{safe_name}' "
        "and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    )
    res = service.files().list(q=query, fields="files(id)", pageSize=1).execute()
    files = res.get("files") or []
    if files:
        fid = files[0]["id"]
        _FOLDER_CACHE[cache_key] = fid
        return fid
    meta = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    fid = service.files().create(body=meta, fields="id").execute()["id"]
    _FOLDER_CACHE[cache_key] = fid
    return fid


def verify_drive_connection() -> tuple[bool, str]:
    if not drive_configured():
        return False, "Faltan variables de Google Drive en .env (ver .env.example)."
    try:
        service = _drive_service()
        root = os.environ["GOOGLE_DRIVE_ROOT_FOLDER_ID"].strip()
        meta = service.files().get(fileId=root, fields="id,name").execute()
        name = meta.get("name") or "carpeta"
        mode = "OAuth (Gmail)" if _oauth_configured() else "cuenta de servicio"
        return True, f"Conectado ({mode}): {name}"
    except Exception:
        log.exception("Drive verify failed")
        if _oauth_configured():
            return False, "OAuth falló. Vuelva a ejecutar scripts/drive_oauth_setup.py con hconsultingcolombia@gmail.com."
        return False, "No se pudo acceder a la carpeta. Compártala con el email de la cuenta de servicio (Editor)."


def upload_file(relative_folder: str, filename: str, data: bytes) -> dict | None:
    """
    Sube a Drive bajo: ROOT / relative_folder / filename
    relative_folder ej. david/5f14abcd
    """
    if not drive_configured():
        log.info("Google Drive no configurado; solo archivo local.")
        return None

    from googleapiclient.http import MediaIoBaseUpload

    service = _drive_service()
    root_id = os.environ["GOOGLE_DRIVE_ROOT_FOLDER_ID"].strip()
    parent = root_id
    for part in [p for p in relative_folder.replace("\\", "/").split("/") if p]:
        parent = _get_or_create_folder(service, parent, part)

    mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    media = MediaIoBaseUpload(io.BytesIO(data), mimetype=mime, resumable=False)
    created = (
        service.files()
        .create(
            body={"name": filename, "parents": [parent]},
            media_body=media,
            fields="id, name, webViewLink, webContentLink",
        )
        .execute()
    )
    return {
        "id": created.get("id"),
        "name": created.get("name"),
        "webUrl": created.get("webViewLink"),
        "downloadUrl": created.get("webContentLink"),
        "path": f"{relative_folder}/{filename}".replace("\\", "/"),
        "provider": "google_drive",
    }
