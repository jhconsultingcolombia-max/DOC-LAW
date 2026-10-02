import mimetypes
import os
import smtplib
import ssl
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path

from dotenv import load_dotenv

from legal_services.public_url import pixel_base_is_local

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def reload_mail_env() -> None:
    if _ENV_FILE.is_file():
        load_dotenv(_ENV_FILE, override=True)


def _smtp_credentials() -> tuple[str, str, str, int, str, str]:
    reload_mail_env()
    host = (os.environ.get("SMTP_HOST") or "").strip()
    port = int(os.environ.get("SMTP_PORT") or "587")
    user = (os.environ.get("SMTP_USER") or "").strip()
    password = (os.environ.get("SMTP_PASSWORD") or "").strip().strip('"').replace(" ", "")
    use_ssl = (os.environ.get("SMTP_USE_SSL") or "").strip().lower() in ("1", "true", "yes")
    from_addr = (os.environ.get("MAIL_FROM") or user or "").strip()
    return host, port, user, password, use_ssl, from_addr


def _mail_from_header(from_addr: str) -> str:
    reload_mail_env()
    name = (os.environ.get("MAIL_FROM_NAME") or "JH Consulting — DOC_LAW").strip()
    return formataddr((name, from_addr)) if from_addr else name


def verify_smtp_connection() -> tuple[bool, str]:
    reload_mail_env()
    if is_dry_run():
        return True, "Listo."
    host, port, user, password, use_ssl, _from = _smtp_credentials()
    if not host or not user or not password:
        return False, "Correo no configurado."
    try:
        if use_ssl:
            with smtplib.SMTP_SSL(host, port or 465, timeout=25) as smtp:
                smtp.login(user, password)
        else:
            with smtplib.SMTP(host, port, timeout=25) as smtp:
                smtp.starttls(context=ssl.create_default_context())
                smtp.login(user, password)
        return True, "Listo."
    except smtplib.SMTPAuthenticationError:
        return False, "No se pudo autenticar el correo de envío."
    except Exception:
        return False, "No se pudo conectar al servidor de correo."


def friendly_smtp_error(exc: Exception) -> str:
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return "No se pudo autenticar el correo de envío."
    return "No se pudo enviar el correo."


def is_dry_run() -> bool:
    reload_mail_env()
    return (os.environ.get("MAIL_DRY_RUN") or "").strip().lower() in ("1", "true", "yes")


def smtp_configured() -> bool:
    reload_mail_env()
    return bool((os.environ.get("SMTP_HOST") or "").strip())


def mail_configured() -> bool:
    """True si puede intentar enviar (SMTP real o simulación explícita)."""
    return is_dry_run() or smtp_configured()


def mail_mode() -> str:
    """simulacion | real | pendiente"""
    if is_dry_run():
        return "simulacion"
    if smtp_configured():
        return "real"
    return "pendiente"


def get_mail_from() -> str:
    """Dirección remitente (MAIL_FROM o SMTP_USER)."""
    *_, from_addr = _smtp_credentials()
    return from_addr


def _attach_file(msg: MIMEMultipart, filename: str, data: bytes, mime_type: str | None = None) -> None:
    mime = mime_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    maintype, _, subtype = mime.partition("/")
    part = MIMEBase(maintype, subtype or "octet-stream")
    part.set_payload(data)
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", "attachment", filename=filename)
    msg.attach(part)


def send_html_email(
    to_addr: str,
    subject: str,
    html_body: str,
    text_body: str | None = None,
    attachments: list[tuple[str, bytes, str | None]] | None = None,
) -> None:
    to_addr = (to_addr or "").strip()
    if not to_addr:
        raise ValueError("Destinatario vacío.")

    reload_mail_env()
    if is_dry_run():
        return

    host, port, user, password, use_ssl, from_addr = _smtp_credentials()
    if not from_addr:
        raise ValueError("Configure MAIL_FROM o SMTP_USER en .env")
    if not host:
        raise ValueError("Configure SMTP_HOST o use MAIL_DRY_RUN=1 para pruebas sin envío real.")
    if not password:
        raise ValueError("Falta SMTP_PASSWORD en .env.")
    use_tls = (os.environ.get("SMTP_USE_TLS") or "1").strip().lower() not in ("0", "false", "no")

    files = attachments or []
    if files:
        msg = MIMEMultipart("mixed")
        alt = MIMEMultipart("alternative")
        if text_body:
            alt.attach(MIMEText(text_body, "plain", "utf-8"))
        alt.attach(MIMEText(html_body, "html", "utf-8"))
        msg.attach(alt)
        for filename, data, mime in files:
            _attach_file(msg, filename, data, mime)
    else:
        msg = MIMEMultipart("alternative")
        if text_body:
            msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))
    msg["Subject"] = subject
    msg["From"] = _mail_from_header(from_addr)
    msg["To"] = to_addr
    msg["Reply-To"] = from_addr
    msg["Auto-Submitted"] = "auto-generated"

    try:
        if use_ssl:
            with smtplib.SMTP_SSL(host, port or 465, timeout=25) as smtp:
                smtp.login(user, password)
                smtp.sendmail(from_addr, [to_addr], msg.as_string())
        else:
            with smtplib.SMTP(host, port, timeout=25) as smtp:
                if use_tls:
                    smtp.starttls(context=ssl.create_default_context())
                smtp.login(user, password)
                smtp.sendmail(from_addr, [to_addr], msg.as_string())
    except Exception as exc:
        raise RuntimeError(friendly_smtp_error(exc)) from exc
