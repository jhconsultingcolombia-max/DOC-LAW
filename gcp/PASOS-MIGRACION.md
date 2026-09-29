# DOC_LAW → Google Cloud (paso a paso)

Migración por fases. **Fase 1** deja la app en Cloud Run; Azure OpenAI y datos persistentes siguen en fases 2–4.

## Fase 0 — Cuenta y proyecto (consola, ~30 min)

1. Entra a [Google Cloud Console](https://console.cloud.google.com) con **hconsultingcolombia@gmail.com**.
2. Crea proyecto, ej. `jh-doc-law`.
3. **Facturación** → activa trial **$300** (tarjeta de verificación).
4. **Presupuestos** → alertas en $50, $100, $250.
5. Instala [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) y ejecuta:
   ```powershell
   gcloud auth login
   gcloud config set project jh-doc-law
   ```

## Fase 1 — Cloud Run (app en internet) ← **empezamos aquí**

1. Desde el repo:
   ```powershell
   cd C:\Users\piolo\Documents\Selector\legal-intake\gcp
   .\deploy_cloud_run.ps1 -ProjectId jh-doc-law -Region us-central1
   ```
2. Abre la URL que imprime el script → `/login`.
3. Usuarios iniciales: `data/pdn/usuarios.csv` (incluido en la imagen). **Casos/notificaciones nuevos en Cloud Run se pierden al redeploy** hasta Fase 3 (Storage).
4. Configura URL pública (pixel de correos):
   ```powershell
   gcloud run services update doc-law --region us-central1 `
     --update-env-vars "LEGAL_PUBLIC_BASE_URL=https://TU-URL.run.app,MAIL_DRY_RUN=0"
   ```
5. Variables SMTP (consola Cloud Run → Editar → Variables, o Secret Manager en Fase 2):
   - `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM`, etc. (copiar de `.env` local).

**Prueba:** `https://TU-URL.run.app/api/health` → `"status":"ok"`.

## Fase 2 — Secretos + Google Drive

1. **Secret Manager** → crea secretos (`smtp-password`, `google-drive-refresh-token`, …).
2. Da permiso a la cuenta de servicio de Cloud Run (`roles/secretmanager.secretAccessor`).
3. Monta secretos en el servicio:
   ```powershell
   gcloud run services update doc-law --region us-central1 `
     --set-secrets "SMTP_PASSWORD=smtp-password:latest,GOOGLE_DRIVE_REFRESH_TOKEN=drive-refresh:latest"
   ```
4. Completa OAuth Drive (local): `scripts/drive_oauth_setup.py` → `GOOGLE_DRIVE_ROOT_FOLDER_ID` en variables.

## Fase 3 — Datos persistentes (Cloud Storage)

Hoy los casos viven en `data/{env}/tenants/`. En Cloud Run el disco es efímero.

Opciones (implementación en código pendiente):

- **A)** Bucket GCS + sync al arranque / al guardar (`LEGAL_DATA_ROOT` apuntando a volumen montado).
- **B)** Cloud Run volume montado desde bucket (GCS FUSE).

Hasta entonces: no redeployar sin backup de datos de prueba.

## Fase 4 — Vertex AI (Gemini 2.5 Flash)

1. API **Vertex AI** habilitada.
2. Cuenta de servicio Cloud Run → rol `roles/aiplatform.user`.
3. Adaptar `legal_services/openai_service.py` (flag `LLM_PROVIDER=vertex`) — pendiente en repo.
4. Variables: `GCP_PROJECT`, `GCP_REGION`, `VERTEX_MODEL=gemini-2.5-flash`.

Azure OpenAI puede convivir hasta validar calidad/coste.

## Fase 5 — Dominio y corte

1. Dominio propio → Cloud Run → **Administrar dominios**.
2. Actualizar `LEGAL_PUBLIC_BASE_URL`.
3. Reducir tráfico en Azure `/doc-law` cuando GCP esté estable.

## Selector (Sofia / TALENT)

Sigue en Azure por ahora. DOC_LAW en GCP va **sin** prefijo `/doc-law` (URL dedicada). Unificar dominios es opcional en Fase 5.
