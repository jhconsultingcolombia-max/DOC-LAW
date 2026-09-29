(() => {
  const syncMsg = document.getElementById("radicados-sync-msg");
  const refreshBtn = document.getElementById("btn-refresh-radicados-dashboard");

  let syncing = false;

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
        window.location.reload();
        return;
      }
      if (syncMsg) {
        syncMsg.textContent = data.error || "No se pudieron actualizar los radicados.";
      }
    } catch {
      if (syncMsg) syncMsg.textContent = "Error al conectar. Intente de nuevo.";
    } finally {
      syncing = false;
      if (refreshBtn) {
        refreshBtn.disabled = false;
        refreshBtn.classList.remove("is-syncing");
      }
    }
  }

  refreshBtn?.addEventListener("click", () => syncRadicados());
})();
