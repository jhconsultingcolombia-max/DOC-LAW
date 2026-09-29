"""
Autoriza Google Drive para hconsultingcolombia@gmail.com (una sola vez).

1. Google Cloud Console → APIs → Drive API habilitada
2. Credenciales → Crear ID de cliente OAuth → Aplicación de escritorio
3. En .env: GOOGLE_DRIVE_CLIENT_ID y GOOGLE_DRIVE_CLIENT_SECRET
4. Ejecutar desde legal-intake:
   ..\\.venv\\Scripts\\python.exe scripts\\drive_oauth_setup.py
5. Iniciar sesión con hconsultingcolombia@gmail.com y pegar GOOGLE_DRIVE_REFRESH_TOKEN en .env
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def main() -> None:
    cid = (os.environ.get("GOOGLE_DRIVE_CLIENT_ID") or "").strip()
    secret = (os.environ.get("GOOGLE_DRIVE_CLIENT_SECRET") or "").strip()
    if not cid or not secret:
        print("Configure GOOGLE_DRIVE_CLIENT_ID y GOOGLE_DRIVE_CLIENT_SECRET en legal-intake/.env")
        sys.exit(1)

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("Instale: pip install google-auth-oauthlib")
        sys.exit(1)

    client_config = {
        "installed": {
            "client_id": cid,
            "client_secret": secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    if not creds.refresh_token:
        print("No se obtuvo refresh_token. Revoke acceso en myaccount.google.com/permissions y repita.")
        sys.exit(1)

    print("\n--- Agregue a legal-intake/.env ---\n")
    print(f"GOOGLE_DRIVE_REFRESH_TOKEN={creds.refresh_token}")
    print("\nCree una carpeta en Drive (ej. DOC_LAW Notificaciones), copie su ID de la URL y:")
    print("GOOGLE_DRIVE_ROOT_FOLDER_ID=...")


if __name__ == "__main__":
    main()
