# Datos DOC_LAW por entorno

| Carpeta | Uso |
|---------|-----|
| **dev/** | Pruebas locales (`LEGAL_ENV=dev` en `.env`) |
| **pdn/** | Producción Azure (`LEGAL_ENV=pdn` en App Service) |

Cada entorno contiene:

- `usuarios.csv` — login, clave, `tenant_id`, nombre del despacho
- `tenants/{tenant_id}/` — casos, clientes, empresas, chat (cada usuario solo ve su `tenant_id`)

Variable opcional `LEGAL_DATA_ROOT`: ruta montada que reemplaza `data/{LEGAL_ENV}` (Azure Files).
