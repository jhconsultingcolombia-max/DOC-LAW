# JH consulting — DOC_LAW (Legal Intake)

Plataforma multi-tenant de recepción inicial de casos jurídicos (Colombia).

## Demo local

```bash
cd legal-intake
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Abrir: http://localhost:5050  
Login demo: **David** / **12345** · **Felipe** / **98765** · **Fredy** / **12345**

Producción (mismo App Service `bechange-chat-mvp`, sin enlace en la home):

https://bechange-chat-mvp.azurewebsites.net/doc-law/login

## Arquitectura (vendible)

```
data/
  dev/   ← pruebas (LEGAL_ENV=dev)
  pdn/   ← producción (LEGAL_ENV=pdn en Azure)
    usuarios.csv | usuarios.xlsx
    tenants/{tenant_id}/
        ├── empresas/{id}/...
        ├── clientes/{id}/...
        └── casos/{case_id}/...
```

Cada usuario solo ve casos de su `tenant_id` (sin cambios).

| Módulo | Estado | Producción |
|--------|--------|------------|
| Login multi-tenant | CSV / Excel | Azure AD B2C |
| Carpetas por cliente | Local / contenedor | Azure Files + Blob |
| Intake wizard | ✅ | Power Apps embed opcional |
| Análisis legal | Plantilla | Azure OpenAI + SUIN-Juriscol |
| Comunicación cliente | Borrador | Outlook + aprobación |

## Despliegue

Reutilizar patrón `bechange-chat-mvp`: Flask + Gunicorn en App Service `Prueba1`.

Variables sugeridas:
- `LEGAL_ENV` → `dev` (local) o `pdn` (Azure)
- `FLASK_SECRET_KEY`
- `LEGAL_DATA_ROOT` → montaje Azure Files (sustituye `data/{LEGAL_ENV}`)
- `AZURE_OPENAI_*` → enriquecimiento jurídico

Sembrar PDN desde tu PC: `scripts/sync_dev_to_pdn_data.ps1` antes de desplegar.

## Usuarios (prueba)

En `data/dev/usuarios.csv` (y `data/pdn/` en producción): columnas `usuario`, `clave`, `tenant_id`, `nombre_despacho`.
