window.legalUrl = function (path) {
  const base = (window.LEGAL_BASE || "").replace(/\/$/, "");
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${base}${p}`;
};

/** fetch con prefijo /doc-law; usar siempre en lugar de fetch(legalUrl(...), init) mal cerrado. */
window.legalFetch = function (path, init) {
  return fetch(window.legalUrl(path), init);
};
