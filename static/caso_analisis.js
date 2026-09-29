(() => {
  const btnIa = document.getElementById("btn-analizar-ia");
  const msg = document.getElementById("save-msg");
  const fileInput = document.getElementById("file-input");
  const pickBtn = document.getElementById("pick-files");

  pickBtn?.addEventListener("click", () => fileInput?.click());

  fileInput?.addEventListener("change", async () => {
    for (const file of fileInput.files) {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("case_id", window.CASE_ID);
      fd.append("tipo", document.getElementById("doc-tipo").value);
      if (window.EMPRESA_ID) fd.append("empresa_id", window.EMPRESA_ID);
      if (window.CLIENT_ID) fd.append("client_id", window.CLIENT_ID);
      const res = await window.legalFetch("/api/upload", { method: "POST", body: fd });
      const data = await res.json();
      if (data.ok) {
        const li = document.createElement("li");
        li.textContent = `✓ ${file.name}`;
        document.getElementById("uploaded-list")?.appendChild(li);
      }
    }
    fileInput.value = "";
  });

  btnIa?.addEventListener("click", async () => {
    btnIa.disabled = true;
    btnIa.textContent = "Analizando documentos…";
    try {
      const res = await window.legalFetch(`/api/casos/${window.CASE_ID}/analizar-ia`, { method: "POST" });
      const data = await res.json();
      if (data.ok) {
        location.reload();
      } else {
        throw new Error(data.error || "Error");
      }
    } catch (err) {
      msg.className = "alert alert-error";
      msg.textContent = err.message;
      msg.classList.remove("hidden");
      btnIa.disabled = false;
      btnIa.textContent = "Analizar documentos con IA";
    }
  });
})();
