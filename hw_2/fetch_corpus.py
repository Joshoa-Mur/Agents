"""Корпус ДЗ 2: права потребителя при покупке в интернет-магазине.

Два документа:
  1. Правила продажи товаров по договору розничной купли-продажи (постановление Правительства
     № 657 от 30.05.2026, действуют с 01.09.2026). Официальный PDF с publication.pravo.gov.ru.
     PDF — скан без текстового слоя, поэтому текст распознан tesseract (rus) и лежит в
     data/corpus/pravila_657_pages.jsonl. Пересоздать: python fetch_corpus.py --ocr
  2. Закон РФ «О защите прав потребителей» № 2300-1, актуальная редакция с consultant.ru, по статьям.


"""
import json, subprocess, sys, tempfile, time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
DATA, PDF_DIR, CORPUS_DIR = HERE / "data", HERE / "data" / "pdf", HERE / "data" / "corpus"
for d in (DATA, PDF_DIR, CORPUS_DIR):
    d.mkdir(parents=True, exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0 (agents-course homework; educational project)"}
PRAVILA = {"doc": "Правила продажи товаров (ПП РФ № 657)",
           "file": "pravila_657.pdf",
           "url": "http://publication.pravo.gov.ru/document/0001202606010077",
           "pdf_url": "http://publication.pravo.gov.ru/file/pdf?eoNumber=0001202606010077"}
ZOZPP = {"doc": "Закон «О защите прав потребителей»",
         "base": "https://www.consultant.ru",
         "index": "https://www.consultant.ru/document/cons_doc_LAW_305/"}


def get(url, binary=False):
    for attempt in range(4):
        try:
            r = requests.get(url, headers=HEADERS, timeout=40)
            if r.status_code == 200:
                return r.content if binary else r.text
            problem = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            problem = type(e).__name__
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"{url}: {problem}")



def pdf_path():
    path = PDF_DIR / PRAVILA["file"]
    if not path.exists():
        data = get(PRAVILA["pdf_url"], binary=True)
        assert data[:5] == b"%PDF-", "вместо PDF пришло что-то другое"
        path.write_bytes(data)
    return path


def ocr_pages(path):
    """Скан → текст по страницам. Нужны pdftoppm (poppler) и tesseract с русским языком."""
    pages = []
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["pdftoppm", "-r", "300", "-gray", "-png", str(path), f"{tmp}/p"], check=True)
        for n, png in enumerate(sorted(Path(tmp).glob("p-*.png")), 1):
            text = subprocess.run(["tesseract", str(png), "-", "-l", "rus"], capture_output=True, text=True, check=True).stdout
            pages.append({"page": n, "text": text})
            print(f"  OCR стр. {n}")
    return pages


def pravila_docs(force_ocr=False):
    path, out = pdf_path(), CORPUS_DIR / "pravila_657_pages.jsonl"
    if force_ocr or not out.exists():
        out.write_text("\n".join(json.dumps(p, ensure_ascii=False) for p in ocr_pages(path)) + "\n", encoding="utf-8")
    pages = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [{"doc": PRAVILA["doc"], "file": PRAVILA["file"], "section": f"стр. {p['page']}", "page": p["page"],
             "url": f"{PRAVILA['url']}#page={p['page']}", "text": p["text"]} for p in pages]


# ---------------------------------------------------------------- Закон о защите прав потребителей

def article_text(html):
    """Текст статьи: абзацы основного блока без вставок «см. предыдущую редакцию» и пометок «в ред. ФЗ»."""
    soup = BeautifulSoup(html, "html.parser")
    body = soup.select_one(".document-page__content")
    if body is None:
        raise RuntimeError("на странице нет текста документа (антибот или поменялась вёрстка)")
    for junk in body.select(".document__insert, .document__edit, .document-page__toc, script, style"):
        junk.decompose()
    lines = [" ".join(p.get_text(" ").split()) for p in body.find_all("p")]
    return "\n".join(l for l in lines if l)


def zozpp_docs():
    out = CORPUS_DIR / "zozpp_articles.jsonl"
    if out.exists():
        return [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines() if l.strip()]
    index = get(ZOZPP["index"])
    toc = BeautifulSoup(index, "html.parser").select(".document-page__toc a")
    docs, chapter = [{"doc": ZOZPP["doc"], "chapter": "", "section": "Преамбула и основные понятия",
                      "url": ZOZPP["index"], "text": article_text(index)}], ""
    for a in toc:
        title = " ".join(a.get_text(" ").split())
        if title.startswith("Глава"):
            chapter = title
            continue
        if not title.startswith("Статья"):
            continue
        url = ZOZPP["base"] + a["href"]
        docs.append({"doc": ZOZPP["doc"], "chapter": chapter, "section": title, "url": url, "text": article_text(get(url))})
        print(f"  {title[:70]}")
        time.sleep(1.0)                      # вежливо: одна страница в секунду
    out.write_text("\n".join(json.dumps(d, ensure_ascii=False) for d in docs) + "\n", encoding="utf-8")
    return docs


if __name__ == "__main__":
    corpus = pravila_docs(force_ocr="--ocr" in sys.argv) + zozpp_docs()
    with (DATA / "corpus.jsonl").open("w", encoding="utf-8") as f:
        for d in corpus:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    by_doc = {}
    for d in corpus:
        by_doc.setdefault(d["doc"], []).append(len(d["text"]))
    for doc, sizes in by_doc.items():
        print(f"{doc:42s} частей: {len(sizes):3d}, символов: {sum(sizes)}")
