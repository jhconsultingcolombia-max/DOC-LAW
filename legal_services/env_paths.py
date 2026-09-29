"""Rutas de datos por entorno: dev (pruebas) y pdn (producción)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def get_legal_env() -> str:
    raw = (os.environ.get("LEGAL_ENV") or "dev").strip().lower()
    return raw if raw in ("dev", "pdn") else "dev"


def environment_data_root() -> Path:
    """
    Carpeta del entorno activo. Contiene usuarios.csv (o usuarios.xlsx) y tenants/.
    LEGAL_DATA_ROOT, si está definido, reemplaza data/{LEGAL_ENV} (p. ej. montaje Azure Files).
    """
    override = (os.environ.get("LEGAL_DATA_ROOT") or "").strip()
    if override:
        return Path(override)
    return ROOT / "data" / get_legal_env()


def tenants_root() -> Path:
    return environment_data_root() / "tenants"


def usuarios_csv_path() -> Path:
    return environment_data_root() / "usuarios.csv"


def usuarios_xlsx_path() -> Path:
    return environment_data_root() / "usuarios.xlsx"
