# -*- coding: utf-8 -*-
"""
scripts/scrape_editais.py

Scraper (versão Actions-ready, mas roda local) — baseado no seu original.

Gera JSON com:
- instituicao: nome (extraído de "Resumo Edital <NOME> 20xx" do título antes da 1ª tabela)
- edital: lista de links PDF dos botões ENTRE a última tabela e o disclaimer "Atenção!" (link_oficial)
- link_oficial: link oficial extraído pelo mesmo padrão do script original
- posted_at: data/hora de publicação (para ordenação no front)

Regras:
- Se NÃO houver link_oficial (disclaimer), DESCARTA o post.
- Se NÃO houver tabelas, DESCARTA o post.
- Se NÃO encontrar nenhum botão PDF no trecho entre (última tabela -> disclaimer), DESCARTA o post.

Saídas:
- data/editais_min.json
- site/data/editais_min.json (cópia para a página)
"""

import json, re, time, hashlib, shutil
from pathlib import Path
from urllib.parse import urljoin, urlparse
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

# ---------------- Config ----------------
LIST_URL = "https://med.estrategia.com/portal/noticias/"
OUT_PATH = Path("data/editais_min.json")
SITE_COPY_PATH = Path("data/editais_min.json")

UA = "ResidMedBot/3.1 (+contato: seu-email)"

S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9"})

ANCHOR_TXT = re.compile(
    r"p[aá]gina oficial da (banca organizadora|institui[cç][aã]o|processo seletivo|sele[cç][aã]o)",
    re.I
)
SOCIAL = ("facebook.com","twitter.com","t.me","linkedin.com","instagram.com","wa.me","tiktok.com","x.com")

PDF_RE = re.compile(r"\.pdf(\?|#|$)", re.I)
AVISO_RE = re.compile(r"^\s*aviso\s*$", re.I)

# ---------------- Utils ----------------
def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

def slugify(s: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", norm(s).lower()).strip("-")
    return base[:80] or hashlib.md5((s or "").encode()).hexdigest()[:10]

def soup_of(url: str) -> BeautifulSoup:
    r = S.get(url, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "lxml")

def build_display_title(first_section_title: str, instituicao_full: str = "", nome_fallback: str = "") -> str:
    """
    Extrai o nome entre 'Resumo Edital' e o ano final, ex.:
      'Resumo Edital Hospital Edmundo Vasconcelos 2026' -> 'Hospital Edmundo Vasconcelos'
    """
    t = (first_section_title or "").strip()
    if t:
        m = re.search(r"(?i)^\s*Resumo\s+Edital\s+(.+?)(?:\s+(?:19|20)\d{2})?\s*$", t, flags=re.I)
        if m:
            return " ".join(m.group(1).split())
    if instituicao_full:
        return " ".join(instituicao_full.split())
    return " ".join((nome_fallback or "").split())

# ---------------- Listagem ----------------
def list_article_urls(limit: int = 30):
    print(f"[i] Lendo listagem: {LIST_URL}")
    soup = soup_of(LIST_URL)
    urls, seen = [], set()
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        if "/portal/noticias/" in href:
            u = urljoin(LIST_URL, href.split("?")[0].split("#")[0])
            if urlparse(u).scheme in ("http", "https") and u not in seen:
                seen.add(u)
                urls.append(u)
    print(f"[i] Encontrados {len(urls)} links; checando {min(limit, len(urls))}.")
    return urls[:limit]

# ---------------- Publicação ----------------
def extract_posted_at(soup: BeautifulSoup) -> str | None:
    """
    Mantém a mesma lógica do original: tenta meta published_time ou <time>.
    Retorna string ISO/whatever estiver no HTML.
    """
    meta_pub = (
        soup.find("meta", {"property": "article:published_time"})
        or soup.find("meta", {"name": "article:published_time"})
        or soup.find("time", {"itemprop": "datePublished"})
    )
    if meta_pub:
        val = (meta_pub.get("content") or meta_pub.get("datetime") or "").strip()
        return val or None
    return None

# ---------------- Link oficial (mesma lógica) ----------------
def extract_official_link_tag(soup: BeautifulSoup, base_url: str):
    """
    Retorna:
      (href_oficial, a_tag_oficial)
    ou (None, None)
    """
    for a in soup.find_all("a", href=True):
        txt = norm(a.get_text(" "))
        if ANCHOR_TXT.search(txt):
            href = urljoin(base_url, a["href"])
            host = (urlparse(href).hostname or "").lower()
            if host and "med.estrategia.com" not in host and not any(s in host for s in SOCIAL):
                return href, a
    return None, None

def find_disclaimer_block(a_tag):
    """
    Tenta achar um "bloco" pai razoável do disclaimer, para servir como limite superior.
    """
    if not a_tag:
        return None
    return a_tag.find_parent(["p", "div", "section", "article", "blockquote"]) or a_tag.parent

# ---------------- Tabelas: obter título da 1ª seção e última tabela ----------------
def last_bold_before(node) -> str | None:
    for prev in node.find_all_previous():
        name = getattr(prev, "name", "")
        if name in ("strong", "b"):
            txt = norm(prev.get_text(" "))
            if txt and not AVISO_RE.match(txt):
                return txt
        if name in ("h2", "h3", "h4"):
            txt = norm(prev.get_text(" "))
            if txt and not AVISO_RE.match(txt):
                return txt
    return None

def first_section_title_from_tables(soup: BeautifulSoup):
    tables = soup.find_all("table")
    if not tables:
        return None, None, None  # (first_title, first_table, last_table)
    first_table = tables[0]
    last_table = tables[-1]
    first_title = last_bold_before(first_table) or "Resumo"
    return first_title, first_table, last_table

# ---------------- Extração dos botões PDF entre última tabela e disclaimer ----------------
def is_pdf_href(href: str) -> bool:
    href = (href or "").strip()
    return bool(href and PDF_RE.search(href))

def extract_pdf_buttons_between(last_table, disclaimer_block, base_url: str):
    """
    Varre os elementos do DOM APÓS last_table, até chegar no disclaimer_block,
    coletando <a class="wp-block-button__link"... href=PDF>.
    """
    if not last_table or not disclaimer_block:
        return []

    pdfs = []
    seen = set()

    for el in last_table.next_elements:
        if el is disclaimer_block:
            break

        # se entrou dentro do disclaimer, pare
        try:
            if hasattr(el, "find_parent") and el.find_parent() is disclaimer_block:
                break
        except Exception:
            pass

        if getattr(el, "name", None) == "a":
            cls = el.get("class") or []
            href = el.get("href", "")
            if "wp-block-button__link" in cls and is_pdf_href(href):
                absu = urljoin(base_url, href)
                if absu not in seen:
                    seen.add(absu)
                    pdfs.append(absu)

    return pdfs

# ---------------- Parse do post ----------------
def parse_post(url: str):
    soup = soup_of(url)

    # título do post (só pra log e fallback)
    title_meta = soup.find("meta", {"property": "og:title"})
    title = title_meta.get("content", "") if title_meta else ""
    if not title:
        h1 = soup.find(["h1", "h2"])
        title = h1.get_text(" ", strip=True) if h1 else url
    title = norm(title)

    posted_at = extract_posted_at(soup) or None
    captured_at = datetime.now(timezone.utc).isoformat()

    # precisa ter tabelas
    first_section_title, _, last_table = first_section_title_from_tables(soup)
    if not last_table:
        print(f"  × DESCARTADO: {title} | sem tabelas")
        return None

    # precisa ter link_oficial (disclaimer)
    link_oficial, a_oficial = extract_official_link_tag(soup, url)
    if not link_oficial:
        print(f"  × DESCARTADO: {title} | link_oficial —")
        return None

    disclaimer_block = find_disclaimer_block(a_oficial)
    if not disclaimer_block:
        print(f"  × DESCARTADO: {title} | disclaimer_block não identificado")
        return None

    # extrair PDFs (botões) entre última tabela e disclaimer
    pdfs = extract_pdf_buttons_between(last_table, disclaimer_block, url)
    if not pdfs:
        print(f"  × DESCARTADO: {title} | sem botões PDF entre tabelas e disclaimer")
        return None

    instituicao = build_display_title(first_section_title or "", instituicao_full="", nome_fallback=title)

    print(f"  ✓ {title} | instituicao={instituicao} | pdfs={len(pdfs)} | oficial=OK")

    return {
        "instituicao": instituicao,
        "edital": pdfs,
        "link_oficial": link_oficial,
        "posted_at": posted_at or captured_at,  # garante ordenação mesmo se faltar meta
        "captured_at": captured_at,
    }

# ---------------- Merge incremental ----------------
def merge(existing: list, new_items: list):
    """
    Dedup por (link_oficial). Se repetir, mantém o mais recente (novo sobrescreve antigo).
    Ordena por posted_at desc.
    """
    by = {}
    for x in existing:
        if isinstance(x, dict) and x.get("link_oficial"):
            by[x["link_oficial"]] = x

    for it in new_items:
        if it.get("link_oficial"):
            by[it["link_oficial"]] = it

    def key(x):
        return (x.get("posted_at") or x.get("captured_at") or "")
    return sorted(by.values(), key=key, reverse=True)

def write_outputs(final: list):
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")

    SITE_COPY_PATH.parent.mkdir(parents=True, exist_ok=True)
    # cópia 1:1
def write_outputs(final: list):
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")

    # Se o site está na raiz, o front lê direto de /data/
    print(f"[i] Gravado {OUT_PATH} ({len(final)} registros).")


    print(f"[i] Gravado {OUT_PATH} e copiado para {SITE_COPY_PATH} ({len(final)} registros).")

def main():
    try:
        existing = json.loads(OUT_PATH.read_text(encoding="utf-8"))
        if not isinstance(existing, list):
            existing = []
    except Exception:
        existing = []

    urls = list_article_urls(limit=30)

    items = []
    for u in urls:
        try:
            it = parse_post(u)
            if it:
                items.append(it)
            time.sleep(0.5)
        except Exception as e:
            print(f"  ! erro em {u}: {e}")

    final = merge(existing, items)
    write_outputs(final)
    print(f"[i] Novos nesta rodada: {len(items)}")

if __name__ == "__main__":
    main()
