(() => {
  const form = document.getElementById("edit-form");
  const msg = document.getElementById("save-msg");

  form?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = document.getElementById("btn-save");
    btn.disabled = true;
    btn.textContent = "Guardando…";

    const ramaSelect = document.getElementById("rama_id");
    const ramaOption = ramaSelect.options[ramaSelect.selectedIndex];

    const payload = {
      titulo: document.getElementById("titulo").value.trim(),
      estado: document.getElementById("estado").value,
      cliente_nombre: document.getElementById("cliente_nombre").value.trim(),
      client_id: document.getElementById("client_id").value.trim(),
      empresa_nombre: document.getElementById("empresa_nombre").value.trim(),
      empresa_id: document.getElementById("empresa_id").value.trim(),
      rama_id: ramaSelect.value,
      rama_nombre: ramaOption?.text !== "— Seleccionar —" ? ramaOption.text : "",
      hechos: document.getElementById("hechos").value.trim(),
      entrevista: document.getElementById("entrevista").value.trim(),
      plazo_urgente: document.getElementById("plazo_urgente").value.trim(),
      procesos_radicados: document.getElementById("procesos_radicados").value.trim(),
      partes: window.CASO_PARTES || [],
    };

    try {
      const res = await window.legalFetch(`/api/casos/${window.CASE_ID}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (data.ok) {
        if (data.caso?.borrador_comunicacion) {
          document.getElementById("preview-comunicacion").textContent = data.caso.borrador_comunicacion;
        }
        msg.className = "alert";
        msg.style.background = "rgba(34,197,94,.15)";
        msg.style.border = "1px solid #22c55e";
        msg.textContent = "Expediente guardado.";
        msg.classList.remove("hidden");
        btn.textContent = "Guardado ✓";
        setTimeout(() => { btn.textContent = "Guardar cambios"; btn.disabled = false; }, 2000);
      } else {
        throw new Error(data.error || "Error");
      }
    } catch (err) {
      msg.className = "alert alert-error";
      msg.textContent = "No se pudo guardar: " + err.message;
      msg.classList.remove("hidden");
      btn.disabled = false;
      btn.textContent = "Guardar cambios";
    }
  });
})();
