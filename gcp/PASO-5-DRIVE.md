# Paso 5 — Google Drive (DOC_LAW en Cloud Run)

## 1. Consola GCP (jh-doc-law)

APIs → habilitar **Google Drive API**.

## 2. OAuth (misma cuenta Gmail)

1. **APIs → Credenciales → Crear ID OAuth → Escritorio**
2. Copiar **Client ID** y **Client secret**
3. En tu PC (`legal-intake/.env` temporal):
   ```
   GOOGLE_DRIVE_CLIENT_ID=...
   GOOGLE_DRIVE_CLIENT_SECRET=...
   ```
4. PowerShell:
   ```powershell
   cd C:\Users\piolo\Documents\Selector\legal-intake
   ..\.venv\Scripts\python.exe scripts\drive_oauth_setup.py
   ```
5. Copiar `GOOGLE_DRIVE_REFRESH_TOKEN=...`

## 3. Carpeta Drive

Crear **DOC_LAW Notificaciones** → copiar ID de la URL `.../folders/XXXX`.

## 4. Secret Manager

| Secreto | Valor |
|---------|--------|
| `google-drive-client-id` | Client ID |
| `google-drive-client-secret` | Client secret |
| `google-drive-refresh-token` | Refresh token |

## 5. Cloud Run

```bash
gcloud run services update doc-law --region us-central1 \
  --update-env-vars "GOOGLE_DRIVE_ROOT_FOLDER_ID=TU_FOLDER_ID" \
  --set-secrets "GOOGLE_DRIVE_CLIENT_ID=google-drive-client-id:latest,GOOGLE_DRIVE_CLIENT_SECRET=google-drive-client-secret:latest,GOOGLE_DRIVE_REFRESH_TOKEN=google-drive-refresh-token:latest"
```

Redeploy si hace falta: `cd ~/DOC-LAW && git pull && gcloud run deploy doc-law --source . --region us-central1 --quiet`
