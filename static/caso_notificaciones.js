(() => {
  const caseId = window.CASO_ID;
  let lastItems = [];
  let listFilter = "todas";
  let caseDocuments = [];
  let selectedPcFile = null;
  let lastMensajePrecargado = "";
  let lastAsuntoSugerido = "";
  let mensajeInitialized = false;

  function adjuntoSummary(n) {
    const list = n.adjuntos || [];
    if (!list.length) return "";
    return `<br/><span class="notif-adj-badge" title="Adjunto">📎 ${escapeHtml(list.map((a) => a.nombre).join(", "))}</span>`;
  }

  function clearAdjuntoPc() {
    selectedPcFile = null;
    const fi = document.getElementById("notif-adjunto");
    if (fi) fi.value = "";
    const box = document.getElementById("notif-adjunto-nombre");
    if (box) {
      box.classList.add("hidden");
      box.innerHTML = "";
    }
  }

  function showAdjuntoPc(file) {
    const box = document.getElementById("notif-adjunto-nombre");
    if (!box || !file) return;
    const mb = (file.size / (1024 * 1024)).toFixed(2);
    box.innerHTML = `<span><strong>Archivo del PC:</strong> ${escapeHtml(file.name)} (${mb} MB)</span>
      <button type="button" class="btn btn-ghost btn-sm" id="notif-clear-adjunto">Quitar</button>`;
    box.classList.remove("hidden");
    document.getElementById("notif-clear-adjunto")?.addEventListener("click", () => {
      clearAdjuntoPc();
    });
  }

  function setPcAdjuntoFile(file) {
    if (!file) return;
    const max = 20 * 1024 * 1024;
    if (file.size > max) {
      alert("El archivo supera 20 MB. Elija uno más pequeño.");
      clearAdjuntoPc();
      return;
    }
    selectedPcFile = file;
    const input = document.getElementById("notif-adjunto");
    if (input && typeof DataTransfer !== "undefined") {
      const dt = new DataTransfer();
      dt.items.add(file);
      input.files = dt.files;
    }
    const sel = document.getElementById("notif-doc-caso");
    if (sel) sel.value = "";
    showAdjuntoPc(file);
  }

  function initAdjuntoUploadUi() {
    const zone = document.getElementById("notif-upload-zone");
    const input = document.getElementById("notif-adjunto");
    document.getElementById("notif-pick-file")?.addEventListener("click", (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      input?.click();
    });
    zone?.addEventListener("click", (ev) => {
      if (ev.target.closest("#notif-pick-file")) return;
      input?.click();
    });
    zone?.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" || ev.key === " ") {
        ev.preventDefault();
        input?.click();
      }
    });
    input?.addEventListener("change", () => {
      const file = input.files?.[0];
      if (file) setPcAdjuntoFile(file);
      else clearAdjuntoPc();
    });
    zone?.addEventListener("dragover", (e) => {
      e.preventDefault();
      zone.classList.add("dragover");
    });
    zone?.addEventListener("dragleave", () => zone.classList.remove("dragover"));
    zone?.addEventListener("drop", (e) => {
      e.preventDefault();
      zone.classList.remove("dragover");
      const file = e.dataTransfer?.files?.[0];
      if (file) setPcAdjuntoFile(file);
    });
  }

  function fillDocumentoSelect(docs) {
    caseDocuments = docs || [];
    const sel = document.getElementById("notif-doc-caso");
    if (!sel) return;
    const current = sel.value;
    sel.innerHTML = `<option value="">— Ninguno —</option>`;
    caseDocuments.forEach((d) => {
      const path = (d.path || "").replace(/\\/g, "/");
      const name = d.nombre || d.name || path.split("/").pop() || path;
      if (!path) return;
      const opt = document.createElement("option");
      opt.value = path;
      opt.textContent = name;
      sel.appendChild(opt);
    });
    if (current && [...sel.options].some((o) => o.value === current)) sel.value = current;
  }

  function llegoAlCorreo(n) {
    return n.estado === "enviado";
  }

  function matchesFilter(n, filter) {
    switch (filter) {
      case "llegaron":
        return llegoAlCorreo(n);
      case "no_llegaron":
        return n.estado === "error";
      case "abiertas":
        return !!n.abierto_en;
      case "sin_abrir":
        return llegoAlCorreo(n) && !n.abierto_en;
      default:
        return true;
    }
  }

  function escapeHtml(text) {
    return (text || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function fmtFecha(iso) {
    if (!iso) return "—";
    return iso.replace("T", " ").slice(0, 16);
  }

  function envioCell(n) {
    if (n.estado === "error") {
      return `<span class="notif-form-msg error">${escapeHtml(n.error_envio || "Error SMTP")}</span>`;
    }
    if (n.estado === "enviado") {
      const t = n.enviado_en || n.creado;
      return t ? `<time datetime="${escapeHtml(t)}">${escapeHtml(fmtFecha(t))}</time>` : "—";
    }
    return "—";
  }

  function aperturaCell(n) {
    if (!n.abierto_en) return "—";
    return `<time datetime="${escapeHtml(n.abierto_en)}">${escapeHtml(fmtFecha(n.abierto_en))}</time>`;
  }

  function renderSummary(_items) {
    const el = document.getElementById("notif-summary");
    if (el) el.textContent = "";
  }

  function showDetail(n) {
    const box = document.getElementById("notif-detail");
    if (!box || !n) return;
    box.classList.remove("hidden");
    const adjLines = (n.adjuntos || [])
      .map((a) => {
        const href = a.path
          ? window.legalUrl(`/caso/${caseId}/documento?path=${encodeURIComponent(a.path)}&download=1`)
          : "#";
        return `<li><a href="${href}" target="_blank" rel="noopener">${escapeHtml(a.nombre)}</a></li>`;
      })
      .join("");
    const adjBlock = adjLines ? `<p><strong>Adjuntos:</strong></p><ul>${adjLines}</ul>` : "";
    const cj = n.campos_juzgado || {};
    const juzgadoFields = [
      ["juzgado_destinatario", "Juzgado (destinatario)"],
      ["demandante", "Demandante"],
      ["demandado", "Demandado"],
      ["radicado", "Radicado"],
      ["firmante_nombre", "Apoderado — nombre"],
      ["firmante_cedula", "Apoderado — cédula"],
      ["firmante_tp", "Apoderado — T.P."],
    ];
    const fieldsHtml = juzgadoFields
      .map(
        ([key, label]) => `<label>${escapeHtml(label)}
          <input type="text" data-juzgado-field="${key}" value="${escapeHtml(cj[key] || "")}" />
        </label>`
      )
      .join("");
    const dlJuzgado = window.legalUrl(
      `/api/casos/${caseId}/notificaciones/${encodeURIComponent(n.id)}/juzgado.docx`
    );
    const dlCitacion = window.legalUrl(
      `/api/casos/${caseId}/notificaciones/${encodeURIComponent(n.id)}/citacion.docx`
    );
    const cloud = n.archivos_drive || n.archivos_onedrive || {};
    const odJ = cloud.juzgado?.webUrl
      ? `<p class="muted"><a href="${escapeHtml(cloud.juzgado.webUrl)}" target="_blank" rel="noopener">Google Drive — memorial juzgado</a></p>`
      : "";
    const odC = cloud.citacion?.webUrl
      ? `<p class="muted"><a href="${escapeHtml(cloud.citacion.webUrl)}" target="_blank" rel="noopener">Google Drive — citación</a></p>`
      : "";
    box.innerHTML = `
      <div class="notif-detail-tabs" role="tablist">
        <button type="button" class="notif-detail-tab is-active" data-notif-tab="mensaje" role="tab">Mensaje</button>
        <button type="button" class="notif-detail-tab" data-notif-tab="descargar" role="tab">Descargar</button>
      </div>
      <div class="notif-detail-panel" data-notif-panel="mensaje">
        <h3>${escapeHtml(n.asunto)}</h3>
        <p class="muted">Para: ${escapeHtml(n.para)}</p>
        ${adjBlock}
        <p style="white-space:pre-wrap">${escapeHtml(n.cuerpo)}</p>
        ${n.error_envio ? `<p class="notif-form-msg error">${escapeHtml(n.error_envio)}</p>` : ""}
      </div>
      <div class="notif-detail-panel hidden" data-notif-panel="descargar">
        <div class="notif-juzgado-form">
          <h4>Memorial al juzgado</h4>
          ${fieldsHtml}
          <label>Solicitud al despacho
            <textarea rows="4" data-juzgado-field="cuerpo_solicitud">${escapeHtml(cj.cuerpo_solicitud || "")}</textarea>
          </label>
          <button type="button" class="btn btn-secondary btn-sm" id="btn-save-juzgado-campos">Guardar cambios</button>
          <p id="juzgado-save-msg" class="notif-form-msg muted"></p>
        </div>
        <div class="notif-dl-actions">
          <a class="btn btn-primary btn-dl-juzgado" href="${dlJuzgado}">Descargar memorial al juzgado (.docx)</a>
          <a class="btn btn-secondary btn-dl-citacion" href="${dlCitacion}">Descargar citación enviada (.docx)</a>
        </div>
        ${odJ}${odC}
      </div>
    `;
    box.dataset.notifId = n.id;
    box.querySelectorAll(".notif-detail-tab").forEach((tab) => {
      tab.addEventListener("click", () => {
        const name = tab.dataset.notifTab;
        box.querySelectorAll(".notif-detail-tab").forEach((t) => t.classList.toggle("is-active", t === tab));
        box.querySelectorAll(".notif-detail-panel").forEach((p) => {
          p.classList.toggle("hidden", p.dataset.notifPanel !== name);
        });
      });
    });
    box.querySelector("#btn-save-juzgado-campos")?.addEventListener("click", () => saveJuzgadoCampos(box, n.id));
    box.querySelector(".btn-dl-juzgado")?.addEventListener("click", (ev) => {
      ev.preventDefault();
      saveJuzgadoCampos(box, n.id, () => {
        window.location.href = dlJuzgado;
      });
    });
  }

  async function saveJuzgadoCampos(box, notifId, thenGo) {
    const msg = box.querySelector("#juzgado-save-msg");
    const campos = {};
    box.querySelectorAll("[data-juzgado-field]").forEach((el) => {
      campos[el.getAttribute("data-juzgado-field")] = el.value.trim();
    });
    try {
      const res = await window.legalFetch(`/api/casos/${caseId}/notificaciones/${encodeURIComponent(notifId)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ campos_juzgado: campos }),
      });
      const data = await res.json();
      if (data.ok) {
        const idx = lastItems.findIndex((x) => x.id === notifId);
        if (idx >= 0) lastItems[idx] = data.notificacion;
        if (msg) msg.textContent = "";
        if (thenGo) thenGo();
      } else if (msg) {
        msg.textContent = data.error || "No se pudo guardar.";
        msg.className = "notif-form-msg error";
      }
    } catch {
      if (msg) {
        msg.textContent = "Error de conexión.";
        msg.className = "notif-form-msg error";
      }
    }
  }

  function renderList(items) {
    lastItems = items || [];
    const tbody = document.getElementById("notif-list");
    if (!tbody) return;
    renderSummary(lastItems);

    if (!lastItems.length) {
      tbody.innerHTML = `<tr><td colspan="6" class="muted">No hay notificaciones enviadas.</td></tr>`;
      document.getElementById("notif-detail")?.classList.add("hidden");
      return;
    }

    const filtered = lastItems
      .map((n, idx) => ({ n, idx }))
      .filter(({ n }) => matchesFilter(n, listFilter));

    if (!filtered.length) {
      tbody.innerHTML = `<tr><td colspan="6" class="muted">Ninguna notificación coincide con este filtro.</td></tr>`;
      return;
    }

    tbody.innerHTML = filtered
      .map(
        ({ n, idx }) => `<tr class="notif-row" data-idx="${idx}">
          <td>${escapeHtml(fmtFecha(n.enviado_en || n.creado))}</td>
          <td>${escapeHtml(n.para)}</td>
          <td>${escapeHtml(n.asunto)}${adjuntoSummary(n)}</td>
          <td>${envioCell(n)}</td>
          <td>${aperturaCell(n)}</td>
          <td><button type="button" class="btn btn-ghost btn-sm btn-notif-ver" title="Ver">&#128065;</button></td>
        </tr>`
      )
      .join("");

    tbody.querySelectorAll(".btn-notif-ver").forEach((btn) => {
      btn.addEventListener("click", () => {
        const row = btn.closest(".notif-row");
        const idx = Number(row?.dataset?.idx);
        showDetail(lastItems[idx]);
      });
    });
  }

  function applyMensajePrecargado(texto, asuntoSugerido) {
    const cuerpoEl = document.getElementById("notif-cuerpo");
    if (cuerpoEl && texto) cuerpoEl.value = texto;
    const asuntoEl = document.getElementById("notif-asunto");
    if (asuntoEl && asuntoSugerido && !asuntoEl.value.trim()) {
      asuntoEl.value = asuntoSugerido;
    }
  }

  function syncParaEnMensaje() {
    const para = document.getElementById("notif-para")?.value.trim();
    const cuerpoEl = document.getElementById("notif-cuerpo");
    if (!para || !cuerpoEl) return;
    const lines = cuerpoEl.value.split("\n");
    const idx = lines.findIndex((l) => /^Dirección:/i.test(l.trim()));
    if (idx >= 0) {
      lines[idx] = `Dirección: ${para}`;
      cuerpoEl.value = lines.join("\n");
    }
  }

  async function loadList() {
    const tbody = document.getElementById("notif-list");
    try {
      const res = await fetch(window.legalUrl(`/api/casos/${caseId}/notificaciones`), {
        credentials: "same-origin",
      });
      const data = await res.json();
      if (data.ok) {
        lastMensajePrecargado = data.mensaje_precargado || "";
        lastAsuntoSugerido = data.asunto_sugerido || "";
        const cuerpoEl = document.getElementById("notif-cuerpo");
        if (lastMensajePrecargado && cuerpoEl && !cuerpoEl.value.trim()) {
          applyMensajePrecargado(lastMensajePrecargado, lastAsuntoSugerido);
        }
        mensajeInitialized = true;
        fillDocumentoSelect(data.documentos_caso);
        renderList(data.items);
      } else if (tbody) {
        tbody.innerHTML = `<tr><td colspan="6">${escapeHtml(data.error || "Error al cargar.")}</td></tr>`;
      }
    } catch {
      if (tbody) tbody.innerHTML = `<tr><td colspan="6">Error de conexión.</td></tr>`;
    }
  }

  async function parseJsonResponse(res) {
    const text = await res.text();
    try {
      return JSON.parse(text);
    } catch {
      return { ok: false, error: text.slice(0, 300) || `Error HTTP ${res.status}` };
    }
  }

  document.getElementById("btn-refresh-notif-list")?.addEventListener("click", loadList);

  document.getElementById("notif-para")?.addEventListener("change", syncParaEnMensaje);
  document.getElementById("notif-para")?.addEventListener("blur", syncParaEnMensaje);

  document.getElementById("notif-doc-caso")?.addEventListener("change", (ev) => {
    if (ev.target.value) clearAdjuntoPc();
  });

  document.querySelectorAll(".notif-filter").forEach((btn) => {
    btn.addEventListener("click", () => {
      listFilter = btn.dataset.filter || "todas";
      document.querySelectorAll(".notif-filter").forEach((b) => b.classList.toggle("is-active", b === btn));
      renderList(lastItems);
    });
  });

  document.getElementById("notif-form")?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const btn = document.getElementById("notif-submit");
    const msg = document.getElementById("notif-form-msg");
    if (!btn || !msg) return;

    syncParaEnMensaje();

    btn.disabled = true;
    msg.textContent = "";
    msg.className = "notif-form-msg muted";

    const para = document.getElementById("notif-para")?.value.trim();
    const asunto = document.getElementById("notif-asunto")?.value.trim();
    const cuerpo = document.getElementById("notif-cuerpo")?.value.trim();
    const fileInput = document.getElementById("notif-adjunto");
    const file = fileInput?.files?.[0] || selectedPcFile;
    const docPath = document.getElementById("notif-doc-caso")?.value?.trim();

    try {
      let res;
      if (file || docPath) {
        const fd = new FormData();
        fd.append("para", para);
        fd.append("asunto", asunto);
        fd.append("cuerpo", cuerpo);
        if (file) fd.append("adjunto", file, file.name);
        else fd.append("documento_path", docPath);
        res = await fetch(window.legalUrl(`/api/casos/${caseId}/notificaciones`), {
          method: "POST",
          credentials: "same-origin",
          body: fd,
        });
      } else {
        res = await window.legalFetch(`/api/casos/${caseId}/notificaciones`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "same-origin",
          body: JSON.stringify({ para, asunto, cuerpo }),
        });
      }
      const data = await parseJsonResponse(res);
      if (data.ok) {
        msg.textContent = "";
        msg.className = "notif-form-msg muted";
        document.getElementById("notif-form")?.reset();
        clearAdjuntoPc();
        applyMensajePrecargado(lastMensajePrecargado, lastAsuntoSugerido);
        await loadList();
        if (data.notificacion) showDetail(data.notificacion);
      } else {
        msg.textContent = data.error || "No se pudo enviar.";
        msg.className = "notif-form-msg error";
        await loadList();
      }
    } catch {
      msg.textContent = "Error de conexión con el servidor.";
      msg.className = "notif-form-msg error";
    }

    btn.disabled = false;
    btn.textContent = "Enviar notificación";
  });

  initAdjuntoUploadUi();

  (async () => {
    await loadList();
    setInterval(loadList, 20000);
  })();
})();
