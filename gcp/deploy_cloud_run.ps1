# Despliegue DOC_LAW en Google Cloud Run (Fase 1 — app sola, sin /doc-law)
param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectId,
    [string]$Region = "us-central1",
    [string]$ServiceName = "doc-law",
    [string]$LegalEnv = "pdn"
)

$ErrorActionPreference = "Stop"
$LegalRoot = Split-Path $PSScriptRoot -Parent

Write-Host "Proyecto: $ProjectId | Region: $Region | Servicio: $ServiceName"

gcloud config set project $ProjectId | Out-Null

$apis = @(
    "run.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com"
)
foreach ($api in $apis) {
    Write-Host "API: $api"
    gcloud services enable $api --quiet | Out-Null
}

Push-Location $LegalRoot
try {
    gcloud run deploy $ServiceName `
        --source . `
        --region $Region `
        --platform managed `
        --allow-unauthenticated `
        --memory 1Gi `
        --cpu 1 `
        --min-instances 0 `
        --max-instances 3 `
        --set-env-vars "LEGAL_ENV=$LegalEnv,LEGAL_URL_PREFIX=,MAIL_DRY_RUN=1" `
        --quiet

    $url = (gcloud run services describe $ServiceName --region $Region --format "value(status.url)").Trim()

    Write-Host "Configurando LEGAL_PUBLIC_BASE_URL=$url"
    gcloud run services update $ServiceName --region $Region `
        --update-env-vars "LEGAL_PUBLIC_BASE_URL=$url" `
        --quiet | Out-Null

    Write-Host ""
    Write-Host "========== PASO 1 LISTO =========="
    Write-Host "URL compartible: $url"
    Write-Host "Login:           $url/login"
    Write-Host "Health:          $url/api/health"
    Write-Host ""
    Write-Host "PASO 2: secretos SMTP + MAIL_DRY_RUN=0 (ver gcp/PASO-2-SECRETOS.md)"
}
finally {
    Pop-Location
}
