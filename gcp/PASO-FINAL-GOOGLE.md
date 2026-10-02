# Terminar migración DOC_LAW en Google

Orden estricto. Un bloque → **listo** → siguiente.

## 1 — Redeploy con Vertex en la imagen

```bash
cd ~/DOC-LAW && git pull
gcloud run deploy doc-law --source . --region us-central1 --allow-unauthenticated --memory 1Gi --quiet
```

## 2 — Secreto Gmail

Consola → **Secret Manager** → crear **`smtp-password`** (contraseña de aplicación Gmail).

## 3 — Script Storage + Vertex + URL

```bash
cd ~/DOC-LAW && git pull
chmod +x gcp/setup-doc-law-gcp.sh
./gcp/setup-doc-law-gcp.sh
```

## 4 — Enlazar secreto SMTP

```bash
gcloud run services update doc-law --region us-central1 \
  --set-secrets "SMTP_PASSWORD=smtp-password:latest"
```

Prueba: notificación desde la app.

## 5 — Google Drive (opcional)

Secret Manager: `google-drive-refresh-token`, `google-drive-client-id`, `google-drive-client-secret`  
Variables: `GOOGLE_DRIVE_ROOT_FOLDER_ID`, etc. (ver `.env.example`).

## 6 — Apagar Azure `/doc-law`

Cuando GCP esté validado, dejar de usar Azure solo para DOC_LAW.
