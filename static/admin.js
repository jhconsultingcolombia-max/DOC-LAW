(() => {
  function escapeHtml(t) {
    return (t || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function fmtNum(n) {
    return Number(n || 0).toLocaleString("es-CO");
  }

  async function loadUsers() {
    const tbody = document.getElementById("admin-users-body");
    try {
      const res = await fetch(window.legalUrl("/api/admin/users"), { credentials: "same-origin" });
      const data = await res.json();
      if (!data.ok) {
        tbody.innerHTML = `<tr><td colspan="7">${escapeHtml(data.error || "Error")}</td></tr>`;
        return;
      }
      if (!data.items.length) {
        tbody.innerHTML = `<tr><td colspan="7" class="muted">Sin usuarios.</td></tr>`;
        return;
      }
      tbody.innerHTML = data.items
        .map(
          (u) => `<tr data-user="${escapeHtml(u.usuario)}">
            <td><strong>${escapeHtml(u.usuario)}</strong><br/><span class="muted">${escapeHtml(u.tenant_id)}</span></td>
            <td><input class="admin-inp" data-field="nombre_despacho" value="${escapeHtml(u.nombre_despacho)}" /></td>
            <td>${u.casos_actuales}${u.max_casos != null ? ` / ${u.max_casos}` : ""}</td>
            <td><input class="admin-inp admin-inp-sm" type="number" min="0" data-field="max_casos" value="${u.max_casos != null ? u.max_casos : ""}" placeholder="∞" /></td>
            <td>${fmtNum(u.tokens_total)}<br/><span class="muted">${u.tokens_llamadas || 0} llamadas</span></td>
            <td><input type="checkbox" data-field="admin" ${u.admin ? "checked" : ""} /></td>
            <td><button type="button" class="btn btn-secondary btn-sm btn-save-user">Guardar</button></td>
          </tr>`
        )
        .join("");

      tbody.querySelectorAll(".btn-save-user").forEach((btn) => {
        btn.addEventListener("click", () => saveRow(btn.closest("tr")));
      });
    } catch {
      tbody.innerHTML = `<tr><td colspan="7">Error de conexión.</td></tr>`;
    }
  }

  async function saveRow(row) {
    const usuario = row?.dataset?.user;
    if (!usuario) return;
    const msg = document.getElementById("admin-global-msg");
    const payload = {
      nombre_despacho: row.querySelector('[data-field="nombre_despacho"]')?.value.trim(),
      max_casos: row.querySelector('[data-field="max_casos"]')?.value,
      admin: row.querySelector('[data-field="admin"]')?.checked ? "1" : "0",
    };
    try {
      const res = await window.legalFetch(`/api/admin/users/${encodeURIComponent(usuario)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (data.ok) {
        msg.textContent = `Guardado: ${usuario}`;
        msg.className = "notif-form-msg success";
        await loadUsers();
      } else {
        msg.textContent = data.error || "No se pudo guardar.";
        msg.className = "notif-form-msg error";
      }
    } catch {
      msg.textContent = "Error de conexión.";
      msg.className = "notif-form-msg error";
    }
  }

  document.getElementById("btn-admin-refresh")?.addEventListener("click", loadUsers);

  document.getElementById("admin-new-user")?.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const msg = document.getElementById("admin-new-msg");
    const payload = {
      usuario: document.getElementById("new-usuario")?.value.trim(),
      clave: document.getElementById("new-clave")?.value,
      nombre_despacho: document.getElementById("new-despacho")?.value.trim(),
      max_casos: document.getElementById("new-max-casos")?.value,
      admin: document.getElementById("new-admin")?.checked ? "1" : "0",
    };
    try {
      const res = await window.legalFetch("/api/admin/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (data.ok) {
        msg.textContent = "Usuario creado.";
        msg.className = "notif-form-msg success";
        ev.target.reset();
        await loadUsers();
      } else {
        msg.textContent = data.error || "Error al crear.";
        msg.className = "notif-form-msg error";
      }
    } catch {
      msg.textContent = "Error de conexión.";
      msg.className = "notif-form-msg error";
    }
  });

  loadUsers();
})();
