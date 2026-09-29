(() => {
  const messagesEl = document.getElementById("chat-messages");
  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");
  const caseSelect = document.getElementById("chat-case-select");
  const docsList = document.getElementById("chat-docs-list");
  const btnClear = document.getElementById("btn-clear-chat");
  const btnSend = document.getElementById("btn-send-chat");
  const noDocsToggle = document.getElementById("chat-no-documents");

  let caseId = window.CHAT_CASE_ID || null;
  let lawOnly = Boolean(window.CHAT_LAW_ONLY);

  function useDocumentsInChat() {
    if (lawOnly) return false;
    if (!noDocsToggle) return true;
    return !noDocsToggle.checked;
  }

  if (noDocsToggle) {
    try {
      noDocsToggle.checked = sessionStorage.getItem("legal_chat_no_docs") === "1";
    } catch (e) {
      /* ignore */
    }
    noDocsToggle.addEventListener("change", () => {
      try {
        sessionStorage.setItem("legal_chat_no_docs", noDocsToggle.checked ? "1" : "0");
      } catch (e) {
        /* ignore */
      }
      refreshMeta();
    });
  }

  function escapeHtml(text) {
    return (text || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function renderMarkdownLite(text) {
    return escapeHtml(text)
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\n/g, "<br>");
  }

  function appendMessage(role, content) {
    const div = document.createElement("div");
    div.className = `chat-bubble chat-${role}`;
    div.innerHTML = renderMarkdownLite(content);
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function loadHistory(history) {
    messagesEl.innerHTML = "";
    (history || []).forEach((m) => appendMessage(m.role, m.content));
  }

  async function refreshMeta() {
    const params = new URLSearchParams();
    if (lawOnly) params.set("modo", "ley");
    else if (caseId) params.set("case_id", caseId);
    if (!useDocumentsInChat()) params.set("use_documents", "0");
    const qs = params.toString() ? `?${params.toString()}` : "";
    const res = await fetch(window.legalUrl(`/api/chat/meta${qs}`));
    const data = await res.json();
    if (data.ok && docsList) {
      if (lawOnly) {
        docsList.innerHTML = "<li>Sin contexto — consulta general de derecho colombiano</li>";
        return;
      }
      if (!useDocumentsInChat()) {
        docsList.innerHTML = "<li>Modo sin archivos — no se envían documentos a la IA</li>";
        return;
      }
      const docs = data.documentos_disponibles || [];
      docsList.innerHTML = docs.length
        ? docs.map((d) => `<li>📄 ${escapeHtml(d)}</li>`).join("")
        : "<li>Sin documentos cargados</li>";
    }
  }

  loadHistory(window.CHAT_HISTORY || []);
  refreshMeta();

  caseSelect?.addEventListener("change", () => {
    const val = caseSelect.value;
    if (val === "__ley__") {
      window.location.href = window.legalUrl("/chat?modo=ley");
    } else if (val) {
      window.location.href = window.legalUrl(`/chat?caso=${encodeURIComponent(val)}`);
    } else {
      window.location.href = window.legalUrl("/chat");
    }
  });

  btnClear?.addEventListener("click", async () => {
    if (!confirm("¿Limpiar toda la conversación?")) return;
    const params = new URLSearchParams();
    if (lawOnly) params.set("modo", "ley");
    else if (caseId) params.set("case_id", caseId);
    const qs = params.toString() ? `?${params.toString()}` : "";
    await window.legalFetch(`/api/chat/history${qs}`, { method: "DELETE" });
    messagesEl.innerHTML = "";
  });

  form?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    appendMessage("user", text);
    input.value = "";
    btnSend.disabled = true;
    btnSend.textContent = "Pensando…";
    try {
      const res = await window.legalFetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          case_id: lawOnly ? null : caseId,
          law_only: lawOnly,
          use_documents: useDocumentsInChat(),
        }),
      });
      const data = await res.json();
      if (data.ok) {
        const reply = (data.reply || "").trim();
        appendMessage("assistant", reply || "(La IA no devolvió texto. Revise .env / cuota Azure OpenAI.)");
        refreshMeta();
      } else {
        appendMessage("assistant", data.error || "Error al consultar la IA.");
      }
    } catch {
      appendMessage("assistant", "Error de conexión.");
    } finally {
      btnSend.disabled = false;
      btnSend.textContent = "Enviar";
    }
  });
})();
