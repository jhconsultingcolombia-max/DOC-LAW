# PASO 1 — Proyecto Google Cloud + primera URL de DOC_LAW

Haz **solo esto** antes del Paso 2 (correo, Drive, Storage, Vertex).

## A. En la consola web (tú)

1. Abre https://console.cloud.google.com con **hconsultingcolombia@gmail.com**.
2. **Selector de proyecto** (arriba) → **Nuevo proyecto**.
   - Nombre: `JH DOC LAW`
   - ID: anota el ID (ej. `jh-doc-law-123456`) → lo usamos como `ProjectId`.
3. **Facturación** → vincula cuenta de facturación (trial **$300 / 90 días**).
4. **Facturación → Presupuestos** → crear presupuesto **$100/mes** con alertas al **50%, 90%, 100%**.

No hace falta activar APIs a mano: el script `deploy_cloud_run.ps1` las enciende.

## B. En tu PC (tú)

1. Instala Google Cloud CLI: https://cloud.google.com/sdk/docs/install  
   (Windows: instalador `.exe`, marcar **Add gcloud to PATH**).
2. Cierra y abre PowerShell, luego:

```powershell
gcloud auth login
gcloud config set project TU_PROJECT_ID
gcloud auth application-default login
```

3. Despliega DOC_LAW desde **GitHub** (Cloud Shell):

```bash
cd ~
git clone https://github.com/jhconsultingcolombia-max/DOC-LAW.git
cd DOC-LAW

gcloud config set project jh-doc-law
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com --quiet

gcloud run deploy doc-law --source . --region us-central1 --platform managed \
  --allow-unauthenticated --memory 1Gi --cpu 1 --min-instances 0 --max-instances 3 \
  --set-env-vars "LEGAL_ENV=pdn,LEGAL_URL_PREFIX=,MAIL_DRY_RUN=1" --quiet

URL=$(gcloud run services describe doc-law --region us-central1 --format='value(status.url)')
gcloud run services update doc-law --region us-central1 --update-env-vars "LEGAL_PUBLIC_BASE_URL=$URL" --quiet
echo "Login: $URL/login"
```

La primera vez tarda **5–15 min** (Cloud Build).

Alternativa local (Windows + gcloud): `legal-intake\gcp\deploy_cloud_run.ps1`.

## C. Comprobar

- Abre `https://....run.app/login`
- Abre `https://....run.app/api/health` → `"status":"ok"`

Guarda la URL `*.run.app`: es la que compartes (sin dominio propio).

## Qué NO hacemos aún

- Dominio jhconsulting
- Secretos SMTP / Drive
- Cloud Storage (datos de casos)
- Vertex / Gemini (seguimos Azure OpenAI hasta Paso 4)

Cuando tengas la URL, continúa con **PASO-2-SECRETOS.md**.
