# PASO 2 — Correo en Cloud Run (después del Paso 1)

Solo cuando `https://....run.app/login` funcione.

## En consola → Secret Manager

1. **Security → Secret Manager → Create secret**
   - `smtp-password` → valor = contraseña de aplicación Gmail.
2. (Opcional luego) `google-drive-refresh-token`, `azure-openai-api-key`.

## Permiso a Cloud Run

1. **Cloud Run → doc-law → Security** → copia la **service account** (ej. `...@...gserviceaccount.com`).
2. **IAM → Grant access** → principal = esa cuenta → rol **Secret Manager Secret Accessor**.

## Actualizar servicio

```powershell
$ProjectId = "TU_PROJECT_ID"
$Region = "us-central1"

gcloud run services update doc-law --region $Region --project $ProjectId `
  --update-env-vars "MAIL_DRY_RUN=0,SMTP_HOST=smtp.gmail.com,SMTP_PORT=587,SMTP_USE_TLS=1,MAIL_FROM=jhconsultingcolombia@gmail.com,SMTP_USER=jhconsultingcolombia@gmail.com" `
  --set-secrets "SMTP_PASSWORD=smtp-password:latest"
```

Prueba: enviar una notificación de prueba desde la app.

Siguiente: **PASO-3-STORAGE.md** (persistir casos).
