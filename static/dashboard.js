(() => {
  const RADICADOS_SYNC_KEY = "legal_radicados_sync_done";

  const alertBox = document.getElementById("radicados-alerta");
  const alertBtn = document.getElementById("radicados-alerta-btn");
  const countEl = document.getElementById("radicados-alerta-count");
  const textEl = document.getElementById("radicados-alerta-text");
  const syncMsg = document.getElementById("radicados-sync-msg");
  const refreshBtn = document.getElementById("btn-refresh-radicados-dashboard");

  let syncing = false;

  function markRadicadosSynced() {
    try {
      sessionStorage.setItem(RADICADOS_SYNC_KEY, "1");
    } catch {
      /* ignore */
    }
  }

  function shouldAutoSyncRadicados() {
    try {
      return !sessionStorage.getItem(RADICADOS_SYNC_KEY);
    } catch {
      return true;
    }
  }

  function showUnread(count) {
    if (!alertBox || !countEl) return;
    if (count <= 0) {
      alertBox.classList.add("hidden");
      return;
    }
    alertBox.classList.remove("hidden");
    countEl.textContent = String(count);
    textEl.textContent =
      count === 1
        ? "Actuación judicial sin leer — clic para revisar"
        : `${count} actuaciones judiciales sin leer — clic para revisar`;
  }

  alertBtn?.addEventListener("click", () => {
    window.location.href = window.legalUrl("/radicados");
  });

  async function loadResumen() {
    const res = await fetch(window.legalUrl("/api/radicados/resumen"));
    const data = await res.json();
    if (data.ok) showUnread(data.no_leidos || 0);
  }

  async function syncRadicados() {
    if (syncing) return;
    syncing = true;
    if (refreshBtn) {
      refreshBtn.disabled = true;
      refreshBtn.classList.add("is-syncing");
    }
    if (syncMsg) syncMsg.textContent = "Actualizando radicados…";
    try {
      const res = await fetch(window.legalUrl("/api/radicados/sincronizar"), { method: "POST" });
      const data = await res.json();
      if (data.ok) {
        markRadicadosSynced();
        showUnread(data.no_leidos || 0);
        if (syncMsg) {
          syncMsg.textContent = data.casos_actualizados
            ? `Radicados actualizados en ${data.casos_actualizados} caso(s).`
            : "Radicados al día.";
        }
      } else if (syncMsg) {
        syncMsg.textContent = data.error || "No se pudieron actualizar los radicados.";
      }
    } catch {
      if (syncMsg) syncMsg.textContent = "Error al conectar. Intente de nuevo.";
      await loadResumen();
    } finally {
      syncing = false;
      if (refreshBtn) {
        refreshBtn.disabled = false;
        refreshBtn.classList.remove("is-syncing");
      }
    }
  }

  refreshBtn?.addEventListener("click", () => syncRadicados());

  (async () => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("radicados_sync") === "1") {
      try {
        sessionStorage.removeItem(RADICADOS_SYNC_KEY);
      } catch {
        /* ignore */
      }
      params.delete("radicados_sync");
      const qs = params.toString();
      const clean = window.location.pathname + (qs ? `?${qs}` : "");
      window.history.replaceState(null, "", clean);
    }

    if (shouldAutoSyncRadicados()) {
      await syncRadicados();
    } else {
      if (syncMsg) syncMsg.textContent = "";
      await loadResumen();
    }
  })();

  document.querySelectorAll(".btn-delete-case").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.dataset.caseId;
      const title = btn.dataset.caseTitle || id;
      const ok = window.confirm(
        `¿Eliminar el expediente "${title}" (${id})?\n\nEsta acción no se puede deshacer.`
      );
      if (!ok) return;
      const res = await window.legalFetch(`/api/casos/${encodeURIComponent(id)}`, { method: "DELETE" });
      const data = await res.json();
      if (data.ok) {
        const row = btn.closest("tr");
        if (row) row.remove();
        if (!document.querySelector("tbody tr")) window.location.reload();
      } else {
        alert(data.error || "No se pudo eliminar el expediente.");
      }
    });
  });
})();
