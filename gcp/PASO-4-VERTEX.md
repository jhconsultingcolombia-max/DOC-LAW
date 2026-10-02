# PASO 4 — IA con Vertex (Gemini 2.5 Flash)

## A. Consola Google (tú)

1. Proyecto **jh-doc-law** → **APIs y servicios** → habilitar **Vertex AI API** (`aiplatform.googleapis.com`).
2. **IAM** → cuenta de servicio de Cloud Run (`doc-law@...gserviceaccount.com`) → rol **Vertex AI User** (`roles/aiplatform.user`).

## B. Variables en Cloud Run

Consola → Cloud Run → **doc-law** → Editar → Variables:

| Variable | Valor |
|----------|--------|
| `LLM_PROVIDER` | `vertex` |
| `GCP_PROJECT` | `jh-doc-law` |
| `GCP_REGION` | `us-central1` |
| `VERTEX_MODEL` | `gemini-2.5-flash` |

O en Cloud Shell:

```bash
gcloud run services update doc-law --region us-central1 \
  --update-env-vars "LLM_PROVIDER=vertex,GCP_PROJECT=jh-doc-law,GCP_REGION=us-central1,VERTEX_MODEL=gemini-2.5-flash"
```

## C. Redeploy con código nuevo

```bash
cd ~/DOC-LAW && git pull
gcloud run deploy doc-law --source . --region us-central1 --quiet
```

## D. Probar

Abre `https://TU-URL.run.app/api/health` → debe mostrar:

```json
"llm_provider": "vertex",
"llm_configured": true,
"llm_model": "gemini-2.5-flash"
```

Luego chat legal o análisis de un caso.

## Local (opcional)

```powershell
gcloud auth application-default login
```

En `.env`: `LLM_PROVIDER=vertex`, `GCP_PROJECT=jh-doc-law`, `GCP_REGION=us-central1`.
