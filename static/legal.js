(() => {
  const ramas = window.RAMAS || [];
  const isEdit = window.MODO === "editar";
  const caseEdit = window.CASE_EDIT || null;
  let step = 0;
  let selectedRama = null;
  let currentCaseId = caseEdit?.case_id || null;
  let saving = false;
  const partes = [];
  const uploaded = [];

  const pages = document.querySelectorAll(".wizard-page");
  const steps = document.querySelectorAll(".step");
  const btnPrev = document.getElementById("btn-prev");
  const btnNext = document.getElementById("btn-next");
  const btnSubmit = document.getElementById("btn-submit");
  const btnSave = document.getElementById("btn-save");
  const saveStatus = document.getElementById("save-status");

  function showStep(n) {
    step = n;
    pages.forEach((p) => p.classList.toggle("active", Number(p.dataset.page) === step));
    steps.forEach((s) => s.classList.toggle("active", Number(s.dataset.step) === step));
    btnPrev.disabled = step === 0;
    btnNext.classList.toggle("hidden", step === pages.length - 1);
    btnSubmit.classList.toggle("hidden", step !== pages.length - 1);
  }

  function setSaveStatus(text, kind = "") {
    if (!saveStatus) return;
    saveStatus.textContent = text;
    saveStatus.className = `save-status ${kind}`.trim();
  }

  function canSaveDraft() {
    const titulo = document.getElementById("titulo")?.value.trim();
    const cliente = document.getElementById("cliente_nombre")?.value.trim();
    return Boolean(currentCaseId || (titulo && cliente));
  }

  function renderRamas() {
    const grid = document.getElementById("rama-grid");
    if (!grid) return;
    grid.innerHTML = ramas
      .map(
        (r) => `
      <div class="rama-card" data-id="${r.id}">
        <strong>${r.nombre}</strong>
        <span>${(r.fuentes || []).slice(0, 2).join(" · ")}</span>
      </div>`
      )
      .join("");
    grid.querySelectorAll(".rama-card").forEach((card) => {
      card.addEventListener("click", () => {
        grid.querySelectorAll(".rama-card").forEach((c) => c.classList.remove("selected"));
        card.classList.add("selected");
        selectedRama = ramas.find((r) => r.id === card.dataset.id);
        const detail = document.getElementById("rama-detail");
        if (selectedRama && detail) {
          detail.classList.remove("hidden");
          detail.innerHTML = `
            <strong>Documentos mínimos</strong>
            <ul>${selectedRama.documentos_minimos.map((d) => `<li>${d}</li>`).join("")}</ul>
            <strong>Plazos típicos</strong>
            <ul>${selectedRama.plazos_tipicos.map((d) => `<li>${d}</li>`).join("")}</ul>
            <p><a href="https://www.suin-juriscol.gov.co/" target="_blank" rel="noopener">Consultar SUIN-Juriscol →</a></p>`;
        }
      });
      if (selectedRama && card.dataset.id === selectedRama.id) {
        card.classList.add("selected");
        card.click();
      }
    });
  }

  function renderPartes() {
    const list = document.getElementById("partes-list");
    if (!list) return;
    list.innerHTML = partes
      .map(
        (p, i) => `
      <li>
        <span><strong>${p.tipo}</strong> — ${p.nombre} ${p.documento ? `(${p.documento})` : ""}</span>
        <button type="button" data-i="${i}">Quitar</button>
      </li>`
      )
      .join("");
    list.querySelectorAll("button").forEach((btn) => {
      btn.addEventListener("click", () => {
        partes.splice(Number(btn.dataset.i), 1);
        renderPartes();
      });
    });
  }

  function renderUploaded() {
    const list = document.getElementById("uploaded-list");
    if (!list) return;
    list.innerHTML = uploaded
      .map((d) => `<li>📄 ${d.name || d.path || "documento"}</li>`)
      .join("");
  }

  function loadEditData() {
    if (!caseEdit) return;
    const set = (id, val) => {
      const el = document.getElementById(id);
      if (el && val != null) el.value = val;
    };
    set("titulo", caseEdit.titulo);
    set("cliente_nombre", caseEdit.cliente_nombre);
    set("client_id", caseEdit.client_id);
    set("empresa_nombre", caseEdit.empresa_nombre);
    set("empresa_id", caseEdit.empresa_id);
    set("hechos", caseEdit.hechos);
    set("entrevista", caseEdit.entrevista);
    set("plazo_urgente", caseEdit.plazo_urgente);
    set("procesos_radicados", caseEdit.procesos_radicados);
    if (caseEdit.partes?.length) partes.push(...caseEdit.partes);
    if (caseEdit.documentos?.length) uploaded.push(...caseEdit.documentos);
    if (caseEdit.rama_id) selectedRama = ramas.find((r) => r.id === caseEdit.rama_id) || null;
    renderPartes();
    renderUploaded();
  }

  document.getElementById("btn-add-parte")?.addEventListener("click", () => {
    const nombre = document.getElementById("parte_nombre").value.trim();
    if (!nombre) return;
    partes.push({
      tipo: document.getElementById("parte_tipo").value,
      nombre,
      documento: document.getElementById("parte_id").value.trim(),
    });
    document.getElementById("parte_nombre").value = "";
    document.getElementById("parte_id").value = "";
    renderPartes();
  });

  const uploadZone = document.getElementById("upload-zone");
  const fileInput = document.getElementById("file-input");
  document.getElementById("pick-files")?.addEventListener("click", () => fileInput?.click());

  async function uploadFile(file) {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("tipo", "marco_trabajo");
    const clientId = document.getElementById("client_id")?.value.trim()
      || document.getElementById("cliente_nombre")?.value.trim();
    const empresaId = document.getElementById("empresa_id")?.value.trim();
    if (clientId) fd.append("client_id", clientId);
    if (empresaId) fd.append("empresa_id", empresaId);
    if (currentCaseId) fd.append("case_id", currentCaseId);
    const res = await window.legalFetch("/api/upload", { method: "POST", body: fd });
    const data = await res.json();
    if (data.ok) {
      uploaded.push({ name: file.name, path: data.path, tipo: "marco_trabajo" });
      renderUploaded();
      if (currentCaseId) await saveProgress({ silent: true });
    }
  }

  fileInput?.addEventListener("change", () => {
    [...fileInput.files].forEach(uploadFile);
    fileInput.value = "";
  });
  uploadZone?.addEventListener("dragover", (e) => {
    e.preventDefault();
    uploadZone.classList.add("dragover");
  });
  uploadZone?.addEventListener("dragleave", () => uploadZone.classList.remove("dragover"));
  uploadZone?.addEventListener("drop", (e) => {
    e.preventDefault();
    uploadZone.classList.remove("dragover");
    [...e.dataTransfer.files].forEach(uploadFile);
  });

  function collectPayload(extra = {}) {
    return {
      titulo: document.getElementById("titulo").value.trim(),
      cliente_nombre: document.getElementById("cliente_nombre").value.trim(),
      client_id: document.getElementById("client_id").value.trim() || document.getElementById("cliente_nombre").value.trim(),
      empresa_nombre: document.getElementById("empresa_nombre").value.trim(),
      empresa_id: document.getElementById("empresa_id").value.trim(),
      rama_id: selectedRama?.id,
      rama_nombre: selectedRama?.nombre,
      hechos: document.getElementById("hechos").value.trim(),
      entrevista: document.getElementById("entrevista").value.trim(),
      plazo_urgente: document.getElementById("plazo_urgente").value.trim(),
      partes,
      procesos_radicados: document.getElementById("procesos_radicados").value.trim(),
      documentos: uploaded,
      ...extra,
    };
  }

  async function saveProgress({ silent = false, finalize = false } = {}) {
    if (saving) return false;
    if (!canSaveDraft()) {
      if (!silent) alert("Complete al menos título y nombre del cliente para guardar.");
      return null;
    }

    saving = true;
    if (!silent) {
      btnSave.disabled = true;
      setSaveStatus("Guardando…");
    }

    const payload = collectPayload(finalize ? { estado: "intake_inicial", draft: false } : { draft: true });

    try {
      let res;
      if (currentCaseId) {
        const qs = finalize ? "" : "?regenerate=0";
        res = await window.legalFetch(`/api/casos/${currentCaseId}${qs}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      } else {
        res = await window.legalFetch("/api/casos/borrador", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      }

      const data = await res.json();
      if (data.ok) {
        currentCaseId = data.caso.case_id;
        if (!isEdit && window.location.pathname.endsWith("/caso/nuevo")) {
          window.history.replaceState(null, "", window.legalUrl(`/caso/${currentCaseId}`));
        }
        const stamp = new Date().toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" });
        setSaveStatus(finalize ? "Expediente guardado" : `Guardado ${stamp}`, "ok");
        return data.caso;
      }
      if (!silent) alert(data.error || "Error al guardar.");
      setSaveStatus("Error al guardar", "err");
      return null;
    } catch {
      if (!silent) alert("Error de conexión.");
      setSaveStatus("Error de conexión", "err");
      return null;
    } finally {
      saving = false;
      btnSave.disabled = false;
    }
  }

  function renderAnalysis(caso) {
    const box = document.getElementById("analysis-result");
    if (!box) return;
    box.classList.remove("hidden");
    const v = caso.viabilidad || {};
    box.innerHTML = `
      <div class="analysis-card">
        <h4>Viabilidad preliminar</h4>
        <p>${v.viabilidad_preliminar || "—"}</p>
      </div>`;
  }

  async function goToStep(n) {
    if (n !== step && n > step && canSaveDraft()) {
      await saveProgress({ silent: true });
    }
    showStep(n);
  }

  function validateStep(s) {
    if (s === 0) {
      if (!document.getElementById("titulo").value.trim() || !document.getElementById("cliente_nombre").value.trim()) {
        alert("Complete título y nombre del cliente.");
        return false;
      }
    }
    if (s === 1 && !selectedRama) {
      alert("Seleccione una rama del derecho.");
      return false;
    }
    if (s === 2 && !document.getElementById("hechos").value.trim()) {
      alert("Describa los hechos del caso.");
      return false;
    }
    return true;
  }

  btnPrev?.addEventListener("click", () => goToStep(step - 1));
  btnNext?.addEventListener("click", async () => {
    if (!validateStep(step)) return;
    await goToStep(step + 1);
  });

  steps.forEach((s) => {
    s.addEventListener("click", () => goToStep(Number(s.dataset.step)));
  });

  btnSave?.addEventListener("click", () => saveProgress({ silent: false }));

  btnSubmit?.addEventListener("click", async () => {
    if (!isEdit) {
      const chk = document.getElementById("aprobacion_abogado");
      if (chk && !chk.checked) {
        alert("Marque la confirmación de revisión del abogado.");
        return;
      }
    }
    if (!validateStep(0) || !validateStep(1) || !validateStep(2)) return;

    btnSubmit.disabled = true;
    btnSubmit.textContent = "Procesando…";
    try {
      if (currentCaseId) {
        const caso = await saveProgress({ silent: true, finalize: true });
        if (!caso) {
          btnSubmit.disabled = false;
          btnSubmit.textContent = isEdit ? "Guardar expediente" : "Crear expediente";
          return;
        }
        if (isEdit) renderAnalysis(caso);
        btnSubmit.textContent = "Guardado ✓";
        setTimeout(() => { window.location.href = window.legalUrl(`/caso/${currentCaseId}/analisis`); }, 1200);
      } else {
        const res = await window.legalFetch("/api/intake", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(collectPayload({ estado: "intake_inicial" })),
        });
        const data = await res.json();
        if (data.ok) {
          btnSubmit.textContent = "Expediente creado ✓";
          setTimeout(() => { window.location.href = window.legalUrl(`/caso/${data.caso.case_id}/analisis`); }, 1200);
        } else {
          alert(data.error || "Error al crear expediente.");
          btnSubmit.disabled = false;
          btnSubmit.textContent = "Crear expediente";
        }
      }
    } catch {
      alert("Error de conexión.");
      btnSubmit.disabled = false;
      btnSubmit.textContent = isEdit ? "Guardar expediente" : "Crear expediente";
    }
  });

  document.getElementById("btn-delete-case")?.addEventListener("click", async () => {
    if (!currentCaseId) return;
    const titulo =
      document.getElementById("titulo")?.value.trim() || caseEdit?.titulo || currentCaseId;
    const ok = window.confirm(
      `¿Eliminar el expediente "${titulo}" (${currentCaseId})?\n\nEsta acción no se puede deshacer.`
    );
    if (!ok) return;
    const res = await window.legalFetch(`/api/casos/${encodeURIComponent(currentCaseId)}`, {
      method: "DELETE",
    });
    const data = await res.json();
    if (data.ok) {
      window.location.href = window.legalUrl("/dashboard");
    } else {
      alert(data.error || "No se pudo eliminar el expediente.");
    }
  });

  loadEditData();
  renderRamas();
  renderPartes();
  showStep(0);
})();
