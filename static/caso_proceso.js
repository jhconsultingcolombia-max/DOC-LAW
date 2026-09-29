(() => {
  const caseId = window.CASO_ID;
  const tipos = ["demanda", "poder", "pruebas", "memorial"];
  const soloNoLeidos = new URLSearchParams(window.location.search).get("solo") === "noleidos";
  let pdfCatalog = [];
  let pdfCatalogAll = [];
  let currentRadicadoNumero = "";
  let currentPdfFileName = "documento.pdf";
  let lastPdfObjectUrl = null;

  const EYE_ICON =
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>';

  function escapeHtml(text) {
    return (text || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function cpnuDocUrl(doc) {
    const params = new URLSearchParams({
      id_reg_documento: String(doc.id_reg_documento || ""),
      id_conexion: String(doc.id_conexion || ""),
      id_reg_actuacion: String(doc.id_reg_actuacion || ""),
      guid: doc.guid || "",
      nombre: doc.nombre || "documento.pdf",
    });
    return window.legalUrl(`/caso/${caseId}/cpnu/documento?${params.toString()}`);
  }

  function buildPdfCatalog(caso) {
    const items = [];
    (caso.radicados || []).forEach((r) => {
      (r.traza || []).forEach((t) => {
        (t.documentos_cpnu || []).forEach((d) => {
          if (!d.id_reg_documento) return;
          items.push({
            key: `cpnu-${d.id_reg_documento}`,
            radicado: r.numero,
            label: `${(r.numero || "").slice(-8)} · ${t.fecha || "—"} · ${d.nombre}`,
            url: cpnuDocUrl(d),
            source: "CPNU",
          });
        });
      });
    });
    (caso.documentos || []).forEach((d) => {
      const name = (d.name || d.path || "").toLowerCase();
      if (!name.endsWith(".pdf") || !d.path) return;
      items.push({
        key: `local-${d.path}`,
        label: d.name || d.path,
        url: window.legalUrl(`/caso/${caseId}/documento?path=${encodeURIComponent(d.path)}`),
        source: "Expediente",
      });
    });
    return items;
  }

  function pdfsForRadicado(r) {
    if (!r) return [];
    return buildPdfCatalog({ radicados: [r], documentos: [] });
  }

  function findRadicado(numero) {
    return (window.CASO_DATA?.radicados || []).find((x) => x.numero === numero);
  }

  function setActiveRadicadoCard(numero) {
    document.querySelectorAll(".radicado-card").forEach((card) => {
      card.classList.toggle("radicado-card-active", card.dataset.numero === numero);
    });
  }

  function sanitizeFilename(name) {
    const base = (name || "documento.pdf").trim();
    const withExt = base.toLowerCase().endsWith(".pdf") ? base : `${base}.pdf`;
    return withExt.replace(/[<>:"/\\|?*\u0000-\u001f]+/g, "_").slice(0, 180);
  }

  function setDownloadReady(enabled, filename) {
    const btn = document.getElementById("btn-download-pdf");
    if (filename) currentPdfFileName = sanitizeFilename(filename);
    if (btn) {
      btn.disabled = !enabled;
      btn.title = enabled ? `Descargar ${currentPdfFileName}` : "Seleccione un PDF cargado";
    }
  }

  function docTitleFromCatalogItem(item) {
    if (!item) return "Documento";
    if (item.nombre) return item.nombre;
    const label = item.label || "";
    const parts = label.split(" · ");
    return parts.length > 1 ? parts[parts.length - 1] : label || "Documento";
  }

  function updateViewerMeta({ docTitle, radicado, caption }) {
    const titleEl = document.getElementById("inline-viewer-title");
    const radEl = document.getElementById("inline-viewer-radicado");
    const capEl = document.getElementById("inline-viewer-caption");
    if (titleEl && docTitle) titleEl.textContent = docTitle;
    if (radEl) {
      const num = radicado || currentRadicadoNumero;
      if (num) {
        radEl.innerHTML = `Radicado: <code>${escapeHtml(num)}</code>`;
        radEl.classList.remove("hidden");
      } else {
        radEl.textContent = "";
        radEl.classList.add("hidden");
      }
    }
    if (capEl && caption !== undefined) capEl.textContent = caption || "";
  }

  function closeInlineViewer() {
    document.getElementById("proceso-inline-viewer")?.classList.add("hidden");
    document.getElementById("inline-pdf-wrap")?.classList.add("hidden");
    document.getElementById("inline-cpnu-wrap")?.classList.add("hidden");
    document.querySelectorAll(".radicado-card").forEach((c) => c.classList.remove("radicado-card-active"));
    if (lastPdfObjectUrl) {
      URL.revokeObjectURL(lastPdfObjectUrl);
      lastPdfObjectUrl = null;
    }
    setDownloadReady(false);
    currentRadicadoNumero = "";
  }

  function scrollToInlineViewer() {
    document.getElementById("proceso-inline-viewer")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function showInlinePdf(catalog, title, caption, numero) {
    pdfCatalog = catalog;
    currentRadicadoNumero = numero || catalog.find((x) => x.radicado)?.radicado || "";
    const shell = document.getElementById("proceso-inline-viewer");
    const docTitle =
      catalog.length === 1
        ? docTitleFromCatalogItem(catalog[0])
        : title && !String(title).startsWith("Radicado ")
          ? title
          : "Documentos del radicado";
    updateViewerMeta({ docTitle, radicado: currentRadicadoNumero, caption });
    shell?.classList.remove("hidden");
    document.getElementById("inline-pdf-wrap")?.classList.remove("hidden");
    document.getElementById("inline-cpnu-wrap")?.classList.add("hidden");
    if (numero) setActiveRadicadoCard(numero);
    renderPdfList();
    scrollToInlineViewer();
  }

  function showInlineCpnu(r) {
    const pendingDocs = (r.traza || []).some(
      (t) => t.con_documentos && !(t.documentos_cpnu || []).length
    );
    const cpnuUrl = r.url_oficial || window.CPNU_URL;
    const shell = document.getElementById("proceso-inline-viewer");
    const embedCap = document.getElementById("cpnu-embed-caption");
    updateViewerMeta({
      docTitle: "Consulta CPNU",
      radicado: r.numero,
      caption: pendingDocs
        ? "Actualice radicados para traer PDF de actuaciones, o use Abrir en CPNU."
        : "Consulta embebida de este radicado.",
    });
    if (embedCap) {
      embedCap.innerHTML = `Si no carga, use <strong>Abrir en CPNU</strong> en la tarjeta del radicado.`;
    }
    const frame = document.getElementById("cpnu-embed-frame");
    if (frame) frame.src = cpnuUrl;
    shell?.classList.remove("hidden");
    document.getElementById("inline-cpnu-wrap")?.classList.remove("hidden");
    document.getElementById("inline-pdf-wrap")?.classList.add("hidden");
    setDownloadReady(false);
    setActiveRadicadoCard(r.numero);
    scrollToInlineViewer();
  }

  function openRadicadoEnPagina(numero) {
    const r = findRadicado(numero);
    if (!r) return;
    const radPdfs = pdfsForRadicado(r);
    if (radPdfs.length) {
      showInlinePdf(radPdfs, `Radicado ${r.numero}`, "Solo documentos de este radicado.", numero);
      return;
    }
    showInlineCpnu(r);
  }

  function openSinglePdfUrl(url, title, caption) {
    showInlinePdf([{ key: "one", label: title || "Documento", url, source: "PDF" }], title || "Documento", caption || "");
  }

  function renderPdfList() {
    const list = document.getElementById("pdf-doc-list");
    const frame = document.getElementById("pdf-viewer-frame");
    const empty = document.getElementById("pdf-viewer-empty");
    if (!list) return;

    if (!pdfCatalog.length) {
      list.innerHTML = "<li class='muted' style='padding:12px'>Sin PDF disponibles. Actualice radicados o suba archivos PDF al caso.</li>";
      if (frame) frame.src = "about:blank";
      if (empty) empty.classList.remove("hidden");
      setDownloadReady(false);
      return;
    }

    list.innerHTML = pdfCatalog
      .map((item, i) => {
        const fname = sanitizeFilename(docTitleFromCatalogItem(item));
        return `<li><button type="button" class="pdf-doc-btn${i === 0 ? " active" : ""}" data-pdf-url="${escapeHtml(item.url)}" data-pdf-name="${escapeHtml(fname)}" data-radicado="${escapeHtml(item.radicado || currentRadicadoNumero || "")}">
            <span class="muted" style="font-size:0.75rem">${escapeHtml(item.source)}</span><br/>
            ${escapeHtml(item.label)}
          </button></li>`;
      })
      .join("");

    list.querySelectorAll(".pdf-doc-btn").forEach((btn, i) => {
      btn.addEventListener("click", () => {
        list.querySelectorAll(".pdf-doc-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        const item = pdfCatalog[i];
        updateViewerMeta({
          docTitle: docTitleFromCatalogItem(item),
          radicado: btn.dataset.radicado || currentRadicadoNumero,
        });
        openPdfUrl(btn.dataset.pdfUrl, btn.dataset.pdfName);
      });
    });

    openPdfUrl(pdfCatalog[0].url, sanitizeFilename(docTitleFromCatalogItem(pdfCatalog[0])));
  }

  function showPdfViewerMessage(html) {
    const frame = document.getElementById("pdf-viewer-frame");
    const empty = document.getElementById("pdf-viewer-empty");
    if (frame) frame.src = "about:blank";
    if (empty) {
      empty.innerHTML = html;
      empty.classList.remove("hidden");
    }
  }

  async function openPdfUrl(url, suggestedName) {
    const frame = document.getElementById("pdf-viewer-frame");
    const empty = document.getElementById("pdf-viewer-empty");
    if (!frame || !url) return;
    if (empty) empty.classList.add("hidden");
    setDownloadReady(false);
    if (suggestedName) currentPdfFileName = sanitizeFilename(suggestedName);
    try {
      const res = await fetch(url, { credentials: "same-origin" });
      const ct = (res.headers.get("content-type") || "").toLowerCase();
      if (!res.ok || ct.includes("application/json")) {
        let msg =
          "El documento no está disponible ahora (CPNU respondió con error). Si ya se sincronizó antes, use «Actualizar radicados» o espere la sincronización automática (8:00, 13:00 y 18:00 hora Colombia).";
        if (ct.includes("json")) {
          try {
            const body = await res.json();
            if (body.error) msg = body.error;
          } catch {
            /* ignore */
          }
        }
        const cpnu = window.CPNU_URL || "https://consultaprocesos.ramajudicial.gov.co/Procesos/NumeroRadicacion";
        showPdfViewerMessage(
          `${escapeHtml(msg)} <a href="${escapeHtml(cpnu)}" target="_blank" rel="noopener">Abrir consulta CPNU</a>`
        );
        setDownloadReady(false);
        return;
      }
      const blob = await res.blob();
      if (lastPdfObjectUrl) URL.revokeObjectURL(lastPdfObjectUrl);
      lastPdfObjectUrl = URL.createObjectURL(blob);
      frame.src = lastPdfObjectUrl;
      setDownloadReady(true, currentPdfFileName);
    } catch {
      showPdfViewerMessage(
        `No se pudo cargar el PDF. <a href="${escapeHtml(window.CPNU_URL)}" target="_blank" rel="noopener">Abrir en CPNU</a>`
      );
      setDownloadReady(false);
    }
  }

  function downloadCurrentPdf() {
    if (!lastPdfObjectUrl) return;
    const a = document.createElement("a");
    a.href = lastPdfObjectUrl;
    a.download = currentPdfFileName;
    a.rel = "noopener";
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  document.getElementById("btn-download-pdf")?.addEventListener("click", downloadCurrentPdf);
  document.getElementById("btn-close-inline-viewer")?.addEventListener("click", closeInlineViewer);

  function renderDocs(caso) {
    tipos.forEach((tipo) => {
      const list = document.getElementById(`docs-${tipo}`);
      if (!list) return;
      const docs = (caso.documentos || []).filter((d) => (d.tipo || "").toLowerCase() === tipo);
      list.innerHTML = docs.length
        ? docs
            .map((d) => {
              const isPdf = (d.name || d.path || "").toLowerCase().endsWith(".pdf");
              const view = isPdf && d.path
                ? ` <button type="button" class="link-btn btn-ver-pdf-local" data-path="${escapeHtml(d.path)}">Ver PDF</button>`
                : "";
              return `<li>📄 ${escapeHtml(d.name || d.path)}${view}</li>`;
            })
            .join("")
        : "<li class='muted'>Sin archivos</li>";
      list.querySelectorAll(".btn-ver-pdf-local").forEach((btn) => {
        btn.addEventListener("click", () => {
          openSinglePdfUrl(
            window.legalUrl(`/caso/${caseId}/documento?path=${encodeURIComponent(btn.dataset.path)}`),
            btn.dataset.path?.split("/").pop() || "Expediente",
            "Archivo del expediente del caso."
          );
        });
      });
    });
  }

  async function toggleLeida(numero, actuacionId, leida) {
    const res = await window.legalFetch(`/api/casos/${caseId}/radicados/actuacion/leida`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ numero, actuacion_id: actuacionId, leida }),
    });
    const data = await res.json();
    if (data.ok) {
      window.CASO_DATA = data.caso;
      pdfCatalogAll = buildPdfCatalog(data.caso);
      pdfCatalog = pdfCatalogAll;
      renderRadicados(data.caso.radicados || []);
    } else {
      alert(data.error || "No se pudo actualizar el estado.");
    }
  }

  function renderTrazaItem(r, t) {
    const aid = t.actuacion_id || "";
    const unread = t.leida === false;
    if (soloNoLeidos && !unread) return "";
    const docs = t.documentos_cpnu || [];
    const docLinks = docs.length
      ? docs
          .map(
            (d) =>
              `<button type="button" class="link-btn traza-doc-link btn-traza-pdf" data-doc="${encodeURIComponent(JSON.stringify(d))}">PDF: ${escapeHtml(d.nombre)}</button>`
          )
          .join("")
      : "";
    return `<li class="traza-item ${unread ? "traza-unread" : "traza-read"}" id="act-${escapeHtml(aid)}">
      <div class="traza-item-main">
        <strong>${escapeHtml(t.fecha || "—")}</strong> — ${escapeHtml(t.actuacion || "")}${
      t.anotacion ? `: ${escapeHtml(t.anotacion)}` : ""
    }
        ${docLinks}
      </div>
      <button type="button" class="btn btn-ghost btn-sm traza-toggle" data-numero="${escapeHtml(r.numero)}" data-aid="${escapeHtml(aid)}" data-leida="${unread ? "0" : "1"}">
        ${unread ? "Marcar leída" : "Marcar no leída"}
      </button>
    </li>`;
  }

  function renderRadicados(radicados) {
    const box = document.getElementById("radicados-list");
    if (!box) return;
    if (!radicados?.length) {
      box.innerHTML = "<p class='muted'>No hay radicados registrados.</p>";
      return;
    }
    box.innerHTML = radicados
      .map((r) => {
        const trazaItems = (r.traza || []).map((t) => renderTrazaItem(r, t)).filter(Boolean);
        const unreadCount = (r.traza || []).filter((t) => t.leida === false).length;
        const trazaHtml = trazaItems.length
          ? `<ul class="traza-list">${trazaItems.join("")}</ul>`
          : "<p class='muted'>Sin traza disponible.</p>";
        const cpnuLink = r.url_oficial || window.CPNU_URL;
        return `
        <article class="radicado-card" data-numero="${escapeHtml(r.numero)}">
          <header>
            <div class="radicado-card-title">
              <code>${escapeHtml(r.numero)}</code>
              ${unreadCount ? `<span class="badge badge-warn">${unreadCount} sin leer</span>` : ""}
            </div>
            <div class="radicado-card-actions">
              <button type="button" class="btn btn-ghost btn-sm btn-icon-eye btn-ver-radicado" data-numero="${escapeHtml(r.numero)}" title="Ver radicado en esta página">${EYE_ICON}</button>
              <a href="${escapeHtml(cpnuLink)}" target="_blank" rel="noopener" class="btn btn-ghost btn-sm">Abrir en CPNU</a>
            </div>
          </header>
          <p><strong>Última actuación:</strong> ${escapeHtml(r.ultima_actuacion || "—")}</p>
          <p><strong>Despacho:</strong> ${escapeHtml(r.despacho || "—")}</p>
          <p class="muted"><strong>Consultado:</strong> ${escapeHtml((r.consultado_en || "").slice(0, 19))}</p>
          ${soloNoLeidos && !trazaItems.length ? "<p class='muted'>Sin actuaciones pendientes en este radicado.</p>" : trazaHtml}
        </article>`;
      })
      .join("");

    box.querySelectorAll(".traza-toggle").forEach((btn) => {
      btn.addEventListener("click", () => {
        toggleLeida(btn.dataset.numero, btn.dataset.aid, btn.dataset.leida !== "1");
      });
    });

    box.querySelectorAll(".btn-ver-radicado").forEach((btn) => {
      btn.addEventListener("click", () => openRadicadoEnPagina(btn.dataset.numero));
    });

    box.querySelectorAll(".btn-traza-pdf").forEach((btn) => {
      btn.addEventListener("click", () => {
        try {
          const doc = JSON.parse(decodeURIComponent(btn.dataset.doc));
          const card = btn.closest(".radicado-card");
          const numero = card?.dataset?.numero || "";
          showInlinePdf(
            [
              {
                key: `one-${doc.id_reg_documento}`,
                label: doc.nombre,
                nombre: doc.nombre,
                url: cpnuDocUrl(doc),
                source: "CPNU",
                radicado: numero,
              },
            ],
            doc.nombre || "Actuación",
            "Documento de actuación CPNU",
            numero
          );
        } catch {
          alert("No se pudo abrir el documento.");
        }
      });
    });

    if (soloNoLeidos && window.location.hash) {
      document.querySelector(window.location.hash)?.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }

  async function reloadCaso() {
    const res = await fetch(window.legalUrl(`/api/casos/${caseId}`));
    const data = await res.json();
    if (data.ok) {
      window.CASO_DATA = data.caso;
      pdfCatalogAll = buildPdfCatalog(data.caso);
      pdfCatalog = pdfCatalogAll;
      renderRadicados(data.caso.radicados || []);
      renderDocs(data.caso);
    }
  }

  document.getElementById("btn-add-radicado")?.addEventListener("click", async () => {
    const numero = document.getElementById("radicado-input")?.value.trim();
    if (!numero) return alert("Ingrese el número de radicado.");
    const res = await window.legalFetch(`/api/casos/${caseId}/radicados`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ numero }),
    });
    const data = await res.json();
    if (data.ok) {
      document.getElementById("radicado-input").value = "";
      window.CASO_DATA = data.caso;
      pdfCatalogAll = buildPdfCatalog(data.caso);
      pdfCatalog = pdfCatalogAll;
      renderRadicados(data.caso.radicados || []);
    } else {
      alert(data.error || "No se pudo agregar el radicado.");
    }
  });

  document.getElementById("btn-refresh-radicados")?.addEventListener("click", async () => {
    const btn = document.getElementById("btn-refresh-radicados");
    btn.disabled = true;
    btn.textContent = "Actualizando…";
    const res = await window.legalFetch(`/api/casos/${caseId}/radicados/actualizar`, { method: "POST" });
    const data = await res.json();
    btn.disabled = false;
    btn.textContent = "Actualizar radicados";
    if (data.ok) {
      if (data.caso) window.CASO_DATA = data.caso;
      pdfCatalogAll = buildPdfCatalog(data.caso || window.CASO_DATA);
      pdfCatalog = pdfCatalogAll;
      renderRadicados(data.radicados || data.caso?.radicados || []);
      if (data.errors?.length) {
        alert(`Algunos radicados no se actualizaron:\n${data.errors.map((e) => e.numero).join(", ")}`);
      }
    } else {
      alert(data.error || "Error al actualizar.");
    }
  });

  document.querySelectorAll(".lit-file-input").forEach((input) => {
    input.addEventListener("change", async () => {
      const file = input.files?.[0];
      if (!file) return;
      const fd = new FormData();
      fd.append("file", file);
      fd.append("case_id", caseId);
      fd.append("tipo", input.dataset.tipo || "general");
      const res = await window.legalFetch("/api/upload", { method: "POST", body: fd });
      const data = await res.json();
      if (data.ok) await reloadCaso();
      else alert(data.error || "Error al subir archivo.");
      input.value = "";
    });
  });

  if (soloNoLeidos) {
    const note = document.createElement("p");
    note.className = "alert alert-info";
    note.textContent = "Mostrando solo actuaciones marcadas como no leídas.";
    document.getElementById("proceso-panel-actuaciones")?.prepend(note);
  }

  pdfCatalogAll = buildPdfCatalog(window.CASO_DATA || {});
  pdfCatalog = pdfCatalogAll;
  renderRadicados(window.CASO_DATA?.radicados || []);
  renderDocs(window.CASO_DATA || {});
})();
