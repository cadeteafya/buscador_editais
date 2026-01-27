const DATA_URL = "../data/editais_min.json";
const PER_PAGE = 10;

const grid = document.getElementById("grid");
const countLabel = document.getElementById("countLabel");

const prevBtn = document.getElementById("prevBtn");
const nextBtn = document.getElementById("nextBtn");
const pageDots = document.getElementById("pageDots");

let items = [];
let page = 1;

function escapeHtml(str) {
  return (str ?? "")
    .toString()
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function globIconSvg() {
  return `
    <svg class="icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20Z" stroke="currentColor" stroke-width="1.8"/>
      <path d="M2 12h20" stroke="currentColor" stroke-width="1.8"/>
      <path d="M12 2c2.7 2.8 4.2 6.2 4.2 10S14.7 19.2 12 22c-2.7-2.8-4.2-6.2-4.2-10S9.3 4.8 12 2Z" stroke="currentColor" stroke-width="1.8"/>
    </svg>
  `;
}

function totalPages() {
  return Math.max(1, Math.ceil(items.length / PER_PAGE));
}

function clampPage(p) {
  const t = totalPages();
  return Math.min(t, Math.max(1, p));
}

function setPage(p) {
  page = clampPage(p);
  render();
  syncPager();
}

function slicePage() {
  const start = (page - 1) * PER_PAGE;
  return items.slice(start, start + PER_PAGE);
}

function render() {
  const t = totalPages();
  const shown = slicePage();

  countLabel.textContent = `${items.length} editais • página ${page} de ${t}`;

  grid.innerHTML = shown.map((it) => {
    const instituicao = escapeHtml(it.instituicao || "INSTITUIÇÃO");
    const pdfs = Array.isArray(it.edital) ? it.edital : [];
    const firstPdf = pdfs[0] || "#";
    const official = it.link_oficial || "#";

    const extraCount = Math.max(0, pdfs.length - 1);
    const pills = [
      `<span class="pill">${pdfs.length} PDF${pdfs.length === 1 ? "" : "s"}</span>`,
      extraCount > 0 ? `<span class="pill">+${extraCount} anexos</span>` : ""
    ].join("");

    return `
      <article class="card">
        <div class="card-top">
          <h2 class="card-title">${instituicao}</h2>
          <a class="primary" href="${firstPdf}" target="_blank" rel="noopener noreferrer">
            ACESSAR EDITAL
            <span class="arrow">→</span>
          </a>
        </div>

        <div class="card-bottom">
          <div class="row">
            <span class="label">PÁGINA OFICIAL</span>
            <a class="icon-btn" href="${official}" target="_blank" rel="noopener noreferrer" aria-label="Abrir página oficial">
              ${globIconSvg()}
            </a>
          </div>

          <div class="small">
            <div class="pills">${pills}</div>
            ${
              pdfs.length > 1
                ? `<a class="icon-btn" href="${pdfs[1]}" target="_blank" rel="noopener noreferrer" aria-label="Abrir segundo PDF">PDF 2</a>`
                : `<span></span>`
            }
          </div>
        </div>
      </article>
    `;
  }).join("");
}

function syncPager() {
  const t = totalPages();
  prevBtn.disabled = page <= 1;
  nextBtn.disabled = page >= t;

  // dots: mostra até 7 indicadores (com foco ao redor da página atual)
  pageDots.innerHTML = "";
  const maxDots = 7;

  let start = Math.max(1, page - Math.floor(maxDots / 2));
  let end = start + maxDots - 1;
  if (end > t) {
    end = t;
    start = Math.max(1, end - maxDots + 1);
  }

  for (let p = start; p <= end; p++) {
    const d = document.createElement("div");
    d.className = "dot" + (p === page ? " active" : "");
    d.title = `Página ${p}`;
    d.addEventListener("click", () => setPage(p));
    pageDots.appendChild(d);
  }
}

async function load() {
  try {
    const res = await fetch(DATA_URL, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (!Array.isArray(data)) throw new Error("JSON não é uma lista");

    // Ordena por nome (bem estável pra UI). Se quiser, depois a gente ordena por data.
    items = data
      .filter(x => x && typeof x === "object")
      .map(x => ({
        instituicao: x.instituicao || "",
        edital: Array.isArray(x.edital) ? x.edital : [],
        link_oficial: x.link_oficial || "",
	posted_at: x.posted_at || ""
      }))
      .filter(x => x.instituicao && x.link_oficial && x.edital.length > 0)
      .sort((a,b) => (b.posted_at || "").localeCompare(a.posted_at || ""));

    page = 1;
    render();
    syncPager();
  } catch (err) {
    console.error(err);
    countLabel.textContent = "Falha ao carregar os dados.";
    grid.innerHTML = `
      <div class="card" style="padding:18px">
        <div style="font-weight:800; margin-bottom:6px;">Não foi possível carregar o JSON</div>
        <div style="color: rgba(27,27,38,0.7); font-size: 13px;">
          Verifique se <code>site/data/editais_min.json</code> existe e está acessível.
        </div>
      </div>
    `;
  }
}

prevBtn.addEventListener("click", () => setPage(page - 1));
nextBtn.addEventListener("click", () => setPage(page + 1));

load();
