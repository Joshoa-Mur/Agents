
import json, re
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_corpus(path=HERE / "data" / "corpus.jsonl"):
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def _meta(doc):
    return {k: doc.get(k, "") for k in ("doc", "file", "chapter", "section", "page", "url")}


def paragraphs(doc):
    """Абзацы документа. В распознанном PDF строки — это строки скана, абзацы разделены пустой строкой;
    в статьях закона один абзац уже одна строка."""
    if doc.get("file"):                                   
        parts = re.split(r"\n\s*\n", doc["text"])
        parts = [" ".join(p.split()) for p in parts]
        parts = [p for p in parts if not re.fullmatch(r"\d{1,3}", p)]   
    else:
        parts = [" ".join(l.split()) for l in doc["text"].splitlines()]
    return [p for p in parts if p]


def chunk_structured(doc, min_len=40):
    """Кусок = абзац: в законе и правилах это пункт или подпункт, одна норма целиком.
    Короткие абзацы (заголовки, «а)», «1.») приклеиваются к следующему, чтобы не терять смысл."""
    chunks, carry = [], ""
    for p in paragraphs(doc):
        text = f"{carry} {p}".strip() if carry else p
        if len(text) < min_len:
            carry = text
            continue
        chunks.append({**_meta(doc), "text": text})
        carry = ""
    if carry:
        chunks.append({**_meta(doc), "text": carry})
    return chunks


def chunk_chars(doc, size=400):
    text = " ".join(doc["text"].split())
    return [{**_meta(doc), "text": text[i:i + size]} for i in range(0, len(text), size)]


def norm(text):
    """Для поиска цитаты в куске: регистр, ё, пунктуация, пробелы не важны."""
    text = str(text).lower().replace("ё", "е")
    return " ".join(re.sub(r"[^\w\s]", " ", text).split())


def has_evidence(chunk, evidence, prefix=120):
    """Кусок содержит цитату-эталон (её начало: длинная цитата может перейти через границу куска)."""
    return norm(evidence)[:prefix] in norm(chunk["text"])
