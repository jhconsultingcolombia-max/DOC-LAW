#!/usr/bin/env bash
# Configura Storage + URL pública + Vertex en Cloud Run (proyecto jh-doc-law).
set -euo pipefail

PROJECT="${GCP_PROJECT:-jh-doc-law}"
REGION="${GCP_REGION:-us-central1}"
SERVICE="${CLOUD_RUN_SERVICE:-doc-law}"
BUCKET="${GCS_BUCKET:-${PROJECT}-data}"

echo "Proyecto: $PROJECT | Servicio: $SERVICE | Bucket: gs://$BUCKET"

gcloud config set project "$PROJECT"

gcloud services enable aiplatform.googleapis.com secretmanager.googleapis.com --quiet

URL="$(gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)')"
if [[ -z "$URL" ]]; then
  echo "No existe el servicio $SERVICE. Despliega primero con gcloud run deploy."
  exit 1
fi

RUN_SA="$(gcloud run services describe "$SERVICE" --region "$REGION" --format='value(spec.template.spec.serviceAccountName)')"
if [[ -z "$RUN_SA" ]]; then
  NUM="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')"
  RUN_SA="${NUM}-compute@developer.gserviceaccount.com"
fi
echo "Service account Cloud Run: $RUN_SA"

gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:${RUN_SA}" \
  --role="roles/aiplatform.user" --quiet >/dev/null

gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:${RUN_SA}" \
  --role="roles/secretmanager.secretAccessor" --quiet >/dev/null

if ! gcloud storage buckets describe "gs://${BUCKET}" &>/dev/null; then
  gcloud storage buckets create "gs://${BUCKET}" --location="$REGION"
fi

if [[ -f "$HOME/DOC-LAW/data/pdn/usuarios.csv" ]]; then
  gcloud storage cp "$HOME/DOC-LAW/data/pdn/usuarios.csv" "gs://${BUCKET}/usuarios.csv"
elif [[ -f "data/pdn/usuarios.csv" ]]; then
  gcloud storage cp "data/pdn/usuarios.csv" "gs://${BUCKET}/usuarios.csv"
fi

gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --member="serviceAccount:${RUN_SA}" \
  --role="roles/storage.objectAdmin" --quiet

ENV_VARS="LEGAL_DATA_ROOT=/mnt/legal-data,LEGAL_PUBLIC_BASE_URL=${URL},LLM_PROVIDER=vertex,GCP_PROJECT=${PROJECT},GCP_REGION=${REGION},VERTEX_MODEL=gemini-2.5-flash,MAIL_DRY_RUN=0,SMTP_HOST=smtp.gmail.com,SMTP_PORT=587,SMTP_USE_TLS=1,MAIL_FROM=jhconsultingcolombia@gmail.com,SMTP_USER=jhconsultingcolombia@gmail.com"

gcloud run services update "$SERVICE" --region "$REGION" \
  --update-env-vars "$ENV_VARS" \
  --add-volume=name=legal-data,type=cloud-storage,bucket="${BUCKET}" \
  --add-volume-mount=volume=legal-data,mount-path=/mnt/legal-data \
  --quiet

echo ""
echo "OK. URL: $URL"
echo "Health: ${URL}/api/health"
echo "Login:  ${URL}/login"
echo ""
echo "Falta: Secret Manager smtp-password y opcional Drive (ver PASO-FINAL-GOOGLE.md)."
