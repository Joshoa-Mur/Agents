import ast
import math
import operator
import re
import subprocess
import sys
import time
from functools import lru_cache
from html.parser import HTMLParser

import requests
from pydantic import BaseModel, Field

# калькулятор 

OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
       ast.Pow: operator.pow, ast.USub: operator.neg, ast.Mod: operator.mod}


def evaluate(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in OPS:
        return OPS[type(node.op)](evaluate(node.left), evaluate(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in OPS:
        return OPS[type(node.op)](evaluate(node.operand))
    raise ValueError("допустимы только числа и арифметика")


class CalcArgs(BaseModel):
    expr: str = Field(description="арифметическое выражение, например 17*23+5")


def calculator(expr: str) -> str:
    try:
        val = evaluate(ast.parse(expr.replace(",", "."), mode="eval").body)
        return str(int(val)) if float(val).is_integer() else f"{val:.4f}".rstrip("0")
    except Exception as e:
        return f"ошибка вычисления: {e}"


# python_exec

class ExecArgs(BaseModel):
    code: str = Field(description="код на Python; результат надо напечатать через print")


def python_exec(code: str) -> str:
    try:
        r = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=5)
    except subprocess.TimeoutExpired:
        return "Код превысил 5 сек"
    out = (r.stdout + r.stderr).strip()
    return out[:5000] if out else "Код исполнился, но ничего не напечатал"


# Википедия: общий запрос

WIKI_HEADERS = {"User-Agent": "agents-course-hw1/1.0 (https://postypashki.ru; educational project)"}
LANGS = ("en", "ru")


def wiki_api(params, lang="en", attempts=3):
    """Один запрос к API Википедии нужного языка, весь JSON-ответ целиком."""
    if lang not in LANGS:
        raise ValueError(f"язык должен быть одним из {LANGS}, а не {lang!r}")
    url = f"https://{lang}.wikipedia.org/w/api.php"
    status = None
    for attempt in range(attempts):
        r = requests.get(url, params={**params, "format": "json", "formatversion": 2},
                         headers=WIKI_HEADERS, timeout=15)
        status = r.status_code
        if status == 200 and r.headers.get("content-type", "").startswith("application/json"):
            return r.json()
        time.sleep(1.0 + attempt)
    raise RuntimeError(f"Википедия ответила {status}")


def wiki(params, attempts=3, lang="en"):
    """Запрос action=query: возвращает только часть "query" ответа."""
    data = wiki_api({"action": "query", **params}, lang, attempts)
    if "query" not in data:
        err = data.get("error") or data.get("warnings") or data
        raise RuntimeError(f"Википедия вернула ответ без результатов: {str(err)[:300]}")
    return data["query"]


# web_search

class SearchArgs(BaseModel):
    query: str = Field(description="короткий поисковый запрос: имя, название, событие, например '2026 in Japan'")
    lang: str = Field(default="en", description="язык Википедии: 'en' для вопросов на английском, "
                                                 "'ru' для вопросов на русском")


def web_search(query: str, lang: str = "en") -> str:
    hits = wiki({"list": "search", "srsearch": query, "srlimit": 3}, lang=lang)["search"]
    if not hits:
        return "nothing found"
    title = hits[0]["title"]
    pages = wiki({"prop": "extracts", "explaintext": 1, "exintro": 1, "titles": title, "redirects": 1},
                 lang=lang)["pages"]
    text = " ".join((pages[0].get("extract") or "").split())[:1500]
    others = ", ".join(h["title"] for h in hits[1:])
    return f"[{title}] {text}" + (f" | другие статьи: {others}" if others else "")


# page_find

# парсим и фильтруем HTML страницы
BLOCK_TAGS = {"p", "div", "li", "tr", "br", "table", "ul", "ol", "dl", "dd", "dt", "caption",
              "blockquote", "h1", "h2", "h3", "h4", "h5", "h6"}
CELL_TAGS = {"td", "th"}
VOID_TAGS = {"br", "img", "hr", "meta", "link", "input", "wbr", "col", "source", "area", "base",
             "embed", "param", "track"}
SKIP_TAGS = {"style", "script"}
SKIP_CLASSES = {"reference", "references", "mw-editsection", "navbox", "navbox-styles", "noprint",
                "mw-references-wrap", "reflist", "metadata"}


class _TextLines(HTMLParser):
    """HTML → текст: """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in VOID_TAGS:
            if tag == "br" and not self.skip:
                self.parts.append("\n")
            return
        if self.skip:
            self.skip += 1
            return
        classes = set((dict(attrs).get("class") or "").split())
        if tag in SKIP_TAGS or classes & SKIP_CLASSES:
            self.skip = 1
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")
        elif tag in CELL_TAGS:
            self.parts.append(" | ")

    def handle_endtag(self, tag):
        if tag in VOID_TAGS:
            return
        if self.skip:
            self.skip -= 1
        elif tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_to_lines(html):
    parser = _TextLines()
    parser.feed(html)
    lines = []
    for raw in "".join(parser.parts).split("\n"):
        line = re.sub(r"(\s*\|\s*)+", " | ", " ".join(raw.split())).strip(" |")
        if len(line) < 3:
            continue
        # длинные абзацы режем на предложения, чтобы возвращать точечно, а не полстатьи
        lines += [s for s in re.split(r"(?<=[.!?])\s+", line) if s] if len(line) > 400 else [line]
    return lines


@lru_cache(maxsize=64)
def page_lines(title, lang="en"):
    """Название статьи после редиректов и её текст по строкам. Кэш: одна страница скачивается один раз."""
    data = wiki_api({"action": "parse", "page": title, "prop": "text", "redirects": 1}, lang)
    if "error" in data:
        return None, []
    return data["parse"]["title"], html_to_lines(data["parse"]["text"])


def _stem(word):
    """Нормализация"""
    w = word.lower().replace("ё", "е").strip()
    return w[:-2] if len(w) > 5 and w.isalpha() else w


class FindArgs(BaseModel):
    title: str = Field(description="точное название статьи Википедии, например из результата web_search")
    keywords: list[str] = Field(description="2-4 ключевых слова, которые должны стоять в нужной строке: "
                                            "имена, названия, даты, термины из вопроса")
    lang: str = Field(default="en", description="язык Википедии: 'en' или 'ru', тот же, что у статьи")


def page_find(title: str, keywords: list[str], lang: str = "en", max_hits: int = 8) -> str:
    stems = [_stem(k) for k in keywords if k.strip()]
    if not stems:
        return "ошибка: нужно хотя бы одно ключевое слово"
    real_title, lines = page_lines(title, lang)
    if real_title is None:
        return f"no such page: {title}"
    need = max(1, math.ceil(len(stems) / 2))          

    def score(line):
        low = line.lower().replace("ё", "е")
        return sum(s in low for s in stems)

    hits = [i for i, line in enumerate(lines) if score(line) >= need]
    note = ""
    if not hits:
        # строгий порог не прошла ни одна строка: отдаём строки с наибольшим числом совпадений,
        # иначе одно лишнее общее слово в keywords прячет нужную строку целиком
        top = max((score(line) for line in lines), default=0)
        if top == 0:
            return f"[{real_title}] нет строк с ключевыми словами {keywords}. Попробуйте другие слова."
        hits = [i for i, line in enumerate(lines) if score(line) == top]
        note = f" (строк с половиной ключевых слов нет, показаны строки с {top} из {len(stems)})"
    best = sorted(hits, key=lambda i: (-score(lines[i]), i))[:max_hits]
    
    keep = sorted({j for i in best for j in range(i - 1, i + 3) if 0 <= j < len(lines)})
    out, prev = [f"[{real_title}] найдено строк: {len(hits)}{note}"], None
    for j in keep:
        if prev is not None and j != prev + 1:
            out.append("…")
        out.append(lines[j])
        prev = j
    return "\n".join(out)[:1900]


# описания для register

DESCRIPTIONS = {
    "calculator": "Считает арифметическое выражение: числа, скобки, + - * / ** %",
    "python_exec": "Выполняет код на Python в отдельном процессе и возвращает то, что он напечатал. "
                   "Удобно для дат и вычислений посложнее арифметики",
    "web_search": "Ищет статью в Википедии и возвращает её вступление и названия ещё двух подходящих статей. "
                  "Для вопросов на русском ставь lang='ru'",
    "page_find": "Читает полный текст статьи Википедии (включая таблицы) и возвращает только строки, "
                 "где встречаются ключевые слова. Используй, когда вступления из web_search не хватает: "
                 "факты о событиях обычно лежат в теле статьи",
}
ARGS = {"calculator": CalcArgs, "python_exec": ExecArgs, "web_search": SearchArgs, "page_find": FindArgs}
