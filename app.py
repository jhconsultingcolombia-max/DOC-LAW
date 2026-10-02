import json
import os
from functools import wraps
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, make_response, redirect, render_template, request, send_file, session, url_for

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

from legal_services.auth_service import authenticate, despacho_name_for_user
from legal_services.user_admin_service import is_admin_user, list_users_overview, upsert_user
from legal_services.case_service import (
    analysis_docx_path,
    analyze_case_with_ai,
    delete_case,
    get_case,
    update_case,
)
from legal_services.openai_service import is_configured
from legal_services.intake_service import load_ramas, process_intake, save_intake_draft
from legal_services.legal_chat_service import clear_chat_history, get_chat_history, get_chat_meta, run_legal_chat
from legal_services.proceso_service import (
    add_radicado,
    count_unread_actuaciones,
    iter_unread_actuaciones,
    refresh_all_tenant_radicados,
    refresh_radicados,
    set_actuacion_leida,
)
from legal_services.env_paths import get_legal_env
from legal_services.mail_service import (
    get_mail_from,
    mail_configured,
    mail_mode,
    pixel_base_is_local,
    verify_smtp_connection,
)
from legal_services.google_drive_storage import drive_configured, verify_drive_connection
from legal_services.notificacion_documentos import generate_citacion, generate_juzgado
from legal_services.notificacion_service import (
    create_and_send,
    get_notificacion,
    list_notificaciones,
    record_open,
    tracking_pixel_bytes,
    update_notificacion,
)
from legal_services.notificacion_template import default_asunto, default_fields, default_mensaje
from legal_services.public_url import public_app_base
from legal_services.tenant_storage import list_cases, save_upload, tenant_root

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "bechange-legal-intake-dev-key")

LEGAL_URL_PREFIX = (os.environ.get("LEGAL_URL_PREFIX") or "").rstrip("/")
if LEGAL_URL_PREFIX:
    app.config["APPLICATION_ROOT"] = LEGAL_URL_PREFIX
    app.config["SESSION_COOKIE_PATH"] = LEGAL_URL_PREFIX
    app.config["SESSION_COOKIE_NAME"] = "bechange_legal_session"


def _current_despacho() -> str:
    u = session.get("usuario") or ""
    return despacho_name_for_user(u, session.get("nombre_despacho") or u)


@app.before_request
def _sync_despacho_session():
    if session.get("usuario"):
        session["nombre_despacho"] = _current_despacho()
        session["is_admin"] = is_admin_user(session["usuario"])


@app.context_processor
def inject_legal_base():
    return {
        "legal_base": LEGAL_URL_PREFIX,
        "app_product_name": "DOC_LAW",
        "legal_env": get_legal_env(),
        "despacho": _current_despacho() if session.get("usuario") else "",
        "is_admin": bool(session.get("is_admin")),
    }


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("tenant_id"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("tenant_id"):
            return redirect(url_for("login"))
        if not session.get("is_admin"):
            abort(403)
        return view(*args, **kwargs)

    return wrapped


@app.route("/")
def index():
    if session.get("tenant_id"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        user = authenticate(request.form.get("usuario", ""), request.form.get("clave", ""))
        if user:
            session["usuario"] = user["usuario"]
            session["tenant_id"] = user["tenant_id"]
            session["nombre_despacho"] = user["nombre_despacho"]
            session["is_admin"] = is_admin_user(user["usuario"])
            tenant_root(user["tenant_id"])
            return redirect(url_for("dashboard", radicados_sync=1))
        error = "Usuario o contraseña incorrectos."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    cases = list_cases(session["tenant_id"])
    return render_template(
        "dashboard.html",
        cases=cases,
        despacho=_current_despacho(),
        usuario=session.get("usuario"),
    )


@app.route("/caso/nuevo")
@login_required
def caso_nuevo():
    return render_template(
        "caso_nuevo.html",
        modo="nuevo",
        caso=None,
        ramas=load_ramas(),
        despacho=_current_despacho(),
    )


@app.route("/api/ramas")
@login_required
def api_ramas():
    return jsonify(load_ramas())


@app.route("/api/casos", methods=["GET"])
@login_required
def api_casos():
    return jsonify(list_cases(session["tenant_id"]))


@app.route("/caso/<case_id>")
@login_required
def caso_ver(case_id: str):
    caso = get_case(session["tenant_id"], case_id)
    if not caso:
        abort(404)
    return render_template(
        "caso_nuevo.html",
        modo="editar",
        caso=caso,
        ramas=load_ramas(),
        despacho=_current_despacho(),
    )


@app.route("/caso/<case_id>/proceso")
@login_required
def caso_proceso(case_id: str):
    caso = get_case(session["tenant_id"], case_id)
    if not caso:
        abort(404)
    return render_template(
        "caso_proceso.html",
        caso=caso,
        despacho=_current_despacho(),
    )


@app.route("/caso/<case_id>/notificaciones")
@login_required
def caso_notificaciones(case_id: str):
    tenant = session["tenant_id"]
    caso = get_case(tenant, case_id)
    if not caso:
        abort(404)
    plantilla = default_fields(caso)
    return render_template(
        "caso_notificaciones.html",
        caso=caso,
        despacho=_current_despacho(),
        mail_mode=mail_mode(),
        mail_configured=mail_configured(),
        mail_from=get_mail_from(),
        pixel_local=pixel_base_is_local(),
        mensaje_precargado=default_mensaje(caso),
        asunto_sugerido=default_asunto(plantilla),
    )


@app.route("/caso/<case_id>/analisis")
@login_required
def caso_analisis(case_id: str):
    caso = get_case(session["tenant_id"], case_id)
    if not caso:
        abort(404)
    return render_template(
        "caso_analisis.html",
        caso=caso,
        despacho=_current_despacho(),
    )


@app.route("/caso/<case_id>/informe.docx")
@login_required
def caso_informe_word(case_id: str):
    caso = get_case(session["tenant_id"], case_id)
    if not caso:
        abort(404)
    docx = analysis_docx_path(session["tenant_id"], case_id)
    if not docx.exists():
        from legal_services.case_service import save_case
        save_case(session["tenant_id"], caso)
        docx = analysis_docx_path(session["tenant_id"], case_id)
    if not docx.exists():
        abort(404)
    filename = f"informe_{case_id}.docx"
    return send_file(docx, as_attachment=True, download_name=filename)


@app.route("/api/intake", methods=["POST"])
@login_required
def api_intake():
    payload = request.get_json(force=True)
    payload["abogado_responsable"] = session.get("usuario")
    try:
        caso = process_intake(session["tenant_id"], payload)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": True, "caso": caso})


@app.route("/api/casos/<case_id>", methods=["GET", "PUT", "DELETE"])
@login_required
def api_caso(case_id: str):
    tenant = session["tenant_id"]
    if request.method == "GET":
        caso = get_case(tenant, case_id)
        if not caso:
            return jsonify({"ok": False, "error": "No encontrado"}), 404
        return jsonify({"ok": True, "caso": caso})
    if request.method == "DELETE":
        if not delete_case(tenant, case_id):
            return jsonify({"ok": False, "error": "No encontrado"}), 404
        return jsonify({"ok": True})
    payload = request.get_json(force=True)
    regenerate = request.args.get("regenerate", "1") not in ("0", "false", "False")
    if "draft" in payload and payload.pop("draft"):
        regenerate = False
        payload.setdefault("estado", "borrador")
    caso = update_case(tenant, case_id, payload, regenerate=regenerate)
    if not caso:
        return jsonify({"ok": False, "error": "No encontrado"}), 404
    return jsonify({"ok": True, "caso": caso})


@app.route("/api/casos/borrador", methods=["POST"])
@login_required
def api_caso_borrador():
    payload = request.get_json(force=True)
    payload["abogado_responsable"] = session.get("usuario")
    case_id = payload.get("case_id")
    try:
        caso = save_intake_draft(session["tenant_id"], payload, case_id)
    except ValueError as exc:
        msg = str(exc)
        code = 400 if "Límite de casos" in msg else 404
        return jsonify({"ok": False, "error": msg}), code
    return jsonify({"ok": True, "caso": caso})


@app.route("/api/casos/<case_id>/radicados", methods=["POST"])
@login_required
def api_add_radicado(case_id: str):
    payload = request.get_json(force=True)
    result = add_radicado(session["tenant_id"], case_id, payload.get("numero", ""), refresh=True)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.route("/api/casos/<case_id>/radicados/actualizar", methods=["POST"])
@login_required
def api_refresh_radicados(case_id: str):
    result = refresh_radicados(session["tenant_id"], case_id)
    if result.get("ok"):
        result["no_leidos"] = count_unread_actuaciones(session["tenant_id"])
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.route("/api/radicados/sincronizar", methods=["POST"])
@login_required
def api_radicados_sincronizar():
    result = refresh_all_tenant_radicados(session["tenant_id"])
    return jsonify(result)


@app.route("/api/radicados/resumen")
@login_required
def api_radicados_resumen():
    tenant = session["tenant_id"]
    items = iter_unread_actuaciones(tenant)
    return jsonify({"ok": True, "no_leidos": len(items), "items": items})


@app.route("/api/casos/<case_id>/radicados/actuacion/leida", methods=["POST"])
@login_required
def api_actuacion_leida(case_id: str):
    payload = request.get_json(force=True)
    result = set_actuacion_leida(
        session["tenant_id"],
        case_id,
        payload.get("numero", ""),
        payload.get("actuacion_id", ""),
        bool(payload.get("leida", True)),
    )
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


def _tenant_file_path(tenant_id: str, rel_path: str) -> Path:
    root = tenant_root(tenant_id).resolve()
    rel = (rel_path or "").replace("\\", "/").lstrip("/")
    path = (root / rel).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        abort(403)
    if not path.is_file():
        abort(404)
    return path


@app.route("/caso/<case_id>/documento")
@login_required
def caso_documento_view(case_id: str):
    if get_case(session["tenant_id"], case_id) is None:
        abort(404)
    rel = request.args.get("path", "")
    path = _tenant_file_path(session["tenant_id"], rel)
    inline = request.args.get("download") != "1"
    mimetype = "application/pdf" if path.suffix.lower() == ".pdf" else None
    return send_file(path, mimetype=mimetype, as_attachment=not inline, download_name=path.name)


@app.route("/caso/<case_id>/cpnu/documento")
@login_required
def caso_cpnu_documento(case_id: str):
    if get_case(session["tenant_id"], case_id) is None:
        abort(404)
    from legal_services.rama_judicial_service import descargar_documento_cpnu

    doc = {
        "id_reg_documento": request.args.get("id_reg_documento", type=int),
        "id_conexion": request.args.get("id_conexion", type=int),
        "id_reg_actuacion": request.args.get("id_reg_actuacion", type=int),
        "guid": request.args.get("guid", ""),
        "nombre": request.args.get("nombre", "documento.pdf"),
    }
    try:
        data, mime = descargar_documento_cpnu(doc)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 502
    inline = request.args.get("download") != "1"
    return send_file(
        BytesIO(data),
        mimetype=mime,
        as_attachment=not inline,
        download_name=doc["nombre"],
    )


@app.route("/radicados")
@login_required
def radicados_inbox():
    items = iter_unread_actuaciones(session["tenant_id"])
    return render_template(
        "radicados.html",
        items=items,
        no_leidos=len(items),
        despacho=_current_despacho(),
        usuario=session.get("usuario"),
    )


@app.route("/api/casos/<case_id>/analizar-ia", methods=["POST"])
@login_required
def api_analizar_ia(case_id: str):
    if not is_configured():
        return jsonify({
            "ok": False,
            "error": "IA no configurada. Vertex: LLM_PROVIDER=vertex y GCP_PROJECT en el servicio.",
        }), 503
    try:
        caso = analyze_case_with_ai(session["tenant_id"], case_id)
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500
    if not caso:
        return jsonify({"ok": False, "error": "No encontrado"}), 404
    return jsonify({"ok": True, "caso": caso})


@app.route("/api/upload", methods=["POST"])
@login_required
def api_upload():
    from legal_services.upload_paths import resolve_upload_rel_path

    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"ok": False, "error": "Archivo requerido"}), 400

    rel_path = request.form.get("path") or resolve_upload_rel_path(
        case_id=request.form.get("case_id"),
        client_id=request.form.get("client_id"),
        empresa_id=request.form.get("empresa_id"),
        tipo=request.form.get("tipo", "general"),
    )
    saved = save_upload(session["tenant_id"], rel_path, file.filename, file.read())

    from legal_services.document_cache import build_ia_markdown
    from legal_services.tenant_storage import tenant_root

    full_path = tenant_root(session["tenant_id"]) / saved.replace("/", "\\")
    if not full_path.is_file():
        full_path = tenant_root(session["tenant_id"]) / saved
    context = (request.form.get("context") or request.form.get("tipo") or "")[:500]
    try:
        build_ia_markdown(full_path, context)
    except Exception:
        pass

    case_id = request.form.get("case_id")
    if case_id:
        caso = get_case(session["tenant_id"], case_id)
        if caso:
            docs = caso.get("documentos") or []
            docs.append({
                "name": file.filename,
                "path": saved.replace("\\", "/"),
                "tipo": request.form.get("tipo", "general"),
            })
            update_case(session["tenant_id"], case_id, {"documentos": docs}, regenerate=False)

    return jsonify({"ok": True, "path": saved})


@app.route("/chat")
@login_required
def chat_legal():
    law_only = request.args.get("modo") == "ley"
    case_id = None if law_only else (request.args.get("caso") or request.args.get("case_id"))
    cases = list_cases(session["tenant_id"])
    if law_only:
        subtitle = "Sin contexto · solo preguntas de ley (Colombia)"
    elif case_id:
        subtitle = "Consulta general · documentos del despacho"
        caso = get_case(session["tenant_id"], case_id)
        if caso:
            subtitle = f"Caso {case_id} · {caso.get('titulo') or 'Sin título'}"
        else:
            case_id = None
            subtitle = "Consulta general · documentos del despacho"
    else:
        subtitle = "Consulta general · documentos del despacho"
    history = get_chat_history(session["tenant_id"], case_id, law_only=law_only)
    show_chat_no_docs = not LEGAL_URL_PREFIX or os.environ.get("LEGAL_CHAT_ALLOW_NO_DOCS") == "1"
    return render_template(
        "chat.html",
        despacho=_current_despacho(),
        cases=cases,
        case_id=case_id,
        law_only=law_only,
        subtitle=subtitle,
        history=history,
        show_chat_no_docs=show_chat_no_docs,
    )


@app.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    if not is_configured():
        return jsonify({
            "ok": False,
            "error": "IA no configurada. Vertex: LLM_PROVIDER=vertex y GCP_PROJECT en el servicio.",
        }), 503
    payload = request.get_json(force=True)
    law_only = bool(payload.get("law_only"))
    use_documents = payload.get("use_documents", True)
    if law_only:
        use_documents = False
    elif use_documents is False and LEGAL_URL_PREFIX and os.environ.get("LEGAL_CHAT_ALLOW_NO_DOCS") != "1":
        use_documents = True
    result = run_legal_chat(
        session["tenant_id"],
        payload.get("message", ""),
        case_id=None if law_only else (payload.get("case_id") or None),
        use_documents=bool(use_documents),
        law_only=law_only,
    )
    status = 200 if result.get("ok") else 400
    if result.get("ok"):
        return jsonify(result)
    if "IA no configurada" in result.get("error", ""):
        status = 503
    return jsonify(result), status


@app.route("/api/chat/meta")
@login_required
def api_chat_meta():
    law_only = request.args.get("modo") == "ley" or request.args.get("law_only") in ("1", "true", "True")
    case_id = None if law_only else (request.args.get("case_id") or None)
    use_documents = request.args.get("use_documents", "1") not in ("0", "false", "False")
    if law_only:
        use_documents = False
    elif not use_documents and LEGAL_URL_PREFIX and os.environ.get("LEGAL_CHAT_ALLOW_NO_DOCS") != "1":
        use_documents = True
    meta = get_chat_meta(
        session["tenant_id"], case_id, use_documents=use_documents, law_only=law_only
    )
    return jsonify({"ok": True, **meta})


@app.route("/api/chat/history", methods=["DELETE"])
@login_required
def api_chat_history_clear():
    law_only = request.args.get("modo") == "ley" or request.args.get("law_only") in ("1", "true", "True")
    case_id = None if law_only else (request.args.get("case_id") or None)
    clear_chat_history(session["tenant_id"], case_id, law_only=law_only)
    return jsonify({"ok": True})


@app.route("/api/mail/verify")
@login_required
def api_mail_verify():
    ok, message = verify_smtp_connection()
    return jsonify({"ok": ok, "message": message})


@app.route("/api/drive/verify")
@login_required
def api_drive_verify():
    if not drive_configured():
        return jsonify(
            {
                "ok": False,
                "configured": False,
                "message": "Faltan GOOGLE_DRIVE_ROOT_FOLDER_ID o GOOGLE_DRIVE_CREDENTIALS_JSON en .env.",
            }
        )
    ok, message = verify_drive_connection()
    return jsonify({"ok": ok, "configured": True, "message": message})


@app.route("/api/casos/<case_id>/notificaciones", methods=["GET", "POST"])
@login_required
def api_caso_notificaciones(case_id: str):
    tenant = session["tenant_id"]
    if get_case(tenant, case_id) is None:
        return jsonify({"ok": False, "error": "No encontrado"}), 404

    caso = get_case(tenant, case_id)

    if request.method == "GET":
        plantilla = default_fields(caso)
        return jsonify(
            {
                "ok": True,
                "items": list_notificaciones(tenant, case_id),
                "documentos_caso": caso.get("documentos") or [],
                "mail_configured": mail_configured(),
                "mail_mode": mail_mode(),
                "mail_from": get_mail_from(),
                "pixel_local": pixel_base_is_local(),
                "public_app_base": public_app_base(),
                "plantilla": plantilla,
                "asunto_sugerido": default_asunto(plantilla),
                "mensaje_precargado": default_mensaje(caso),
            }
        )

    documento_path = None
    upload_name = None
    upload_data = None
    para = asunto = cuerpo = ""
    plantilla_campos = None

    if request.content_type and "multipart/form-data" in request.content_type:
        para = request.form.get("para", "")
        asunto = request.form.get("asunto", "")
        cuerpo = request.form.get("cuerpo", "")
        raw_plantilla = request.form.get("plantilla_campos")
        if raw_plantilla:
            plantilla_campos = json.loads(raw_plantilla)
        documento_path = (request.form.get("documento_path") or "").strip() or None
        up = request.files.get("adjunto")
        if up and up.filename:
            upload_name = up.filename
            upload_data = up.read()
    else:
        payload = request.get_json(force=True) or {}
        para = payload.get("para", "")
        asunto = payload.get("asunto", "")
        cuerpo = payload.get("cuerpo", "")
        plantilla_campos = payload.get("plantilla_campos")
        documento_path = (payload.get("documento_path") or "").strip() or None

    try:
        item = create_and_send(
            tenant,
            case_id,
            para,
            asunto,
            cuerpo,
            session.get("usuario") or "",
            request_root=request.url_root.rstrip("/"),
            documento_path=documento_path,
            upload_name=upload_name,
            upload_data=upload_data,
            plantilla_campos=plantilla_campos,
        )
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 502
    return jsonify({"ok": True, "notificacion": item})


@app.route("/api/casos/<case_id>/notificaciones/<notif_id>", methods=["PATCH"])
@login_required
def patch_notificacion(case_id: str, notif_id: str):
    tenant = session["tenant_id"]
    if get_case(tenant, case_id) is None:
        return jsonify({"ok": False, "error": "No encontrado"}), 404
    payload = request.get_json(force=True) or {}
    item = update_notificacion(tenant, case_id, notif_id, payload)
    if not item:
        return jsonify({"ok": False, "error": "Notificación no encontrada"}), 404
    return jsonify({"ok": True, "notificacion": item, "campos_juzgado": item.get("campos_juzgado")})


@app.route("/api/casos/<case_id>/notificaciones/<notif_id>/juzgado.docx")
@login_required
def download_notificacion_juzgado(case_id: str, notif_id: str):
    tenant = session["tenant_id"]
    if get_case(tenant, case_id) is None:
        abort(404)
    path, _ = generate_juzgado(tenant, case_id, notif_id)
    return send_file(
        path,
        as_attachment=True,
        download_name=f"Constancia_al_juzgado_{notif_id}.docx",
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.route("/api/casos/<case_id>/notificaciones/<notif_id>/citacion.docx")
@login_required
def download_notificacion_citacion(case_id: str, notif_id: str):
    tenant = session["tenant_id"]
    if get_case(tenant, case_id) is None:
        abort(404)
    path = generate_citacion(tenant, case_id, notif_id)
    return send_file(
        path,
        as_attachment=True,
        download_name=f"Citacion_enviada_{notif_id}.docx",
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.route("/track/n/<token>.png")
def track_notificacion_open(token: str):
    record_open(token, request.headers.get("X-Forwarded-For", request.remote_addr), request.user_agent.string)
    resp = make_response(tracking_pixel_bytes())
    resp.headers["Content-Type"] = "image/png"
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return resp


@app.route("/admin")
@admin_required
def admin_panel():
    return render_template(
        "admin.html",
        despacho=_current_despacho(),
        usuario=session.get("usuario"),
    )


@app.route("/api/admin/users", methods=["GET"])
@admin_required
def api_admin_users_list():
    return jsonify({"ok": True, "items": list_users_overview()})


@app.route("/api/admin/users", methods=["POST"])
@admin_required
def api_admin_users_create():
    payload = request.get_json(force=True) or {}
    usuario = (payload.get("usuario") or "").strip()
    try:
        item = upsert_user(usuario, payload)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": True, "user": item})


@app.route("/api/admin/users/<usuario>", methods=["PUT"])
@admin_required
def api_admin_users_update(usuario: str):
    payload = request.get_json(force=True) or {}
    try:
        item = upsert_user(usuario, payload)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": True, "user": item})


@app.route("/api/health")
def health():
    from legal_services.openai_service import active_model_label, is_configured, llm_provider

    return jsonify(
        {
            "service": "jh-consulting-doc-law",
            "status": "ok",
            "llm_provider": llm_provider(),
            "llm_configured": is_configured(),
            "llm_model": active_model_label() if is_configured() else None,
        }
    )


if __name__ == "__main__":
    app.run(debug=True, port=5050)
