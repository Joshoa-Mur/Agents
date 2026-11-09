import argparse, json, os, random, re, sys
from pathlib import Path

import requests
from dotenv import load_dotenv

from chunks import chunk_structured, load_corpus, norm

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()
HERE = Path(__file__).resolve().parent
URL = "https://openrouter.ai/api/v1/chat/completions"
HEADERS = {"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}", "X-Title": "agents-course-hw2-questions"}

# пункты, которые важны покупателю интернет-магазина: возврат, обмен, недостатки, сроки, деньги
TOPIC = re.compile(r"возврат|обмен|недостат|срок|дн|гаранти|дистанцион|доставк|денежн|сумм|неустойк|ремонт|заказ|отказ", re.I)

PROMPT = """Ниже пункт российского нормативного акта о продаже товаров.
Придумай ОДИН вопрос, который мог бы задать покупатель интернет-магазина или оператор поддержки,
и короткий ответ на него.

Правила:
- вопрос понятен без текста пункта: назови предмет («по Закону о защите прав потребителей», «по Правилам продажи товаров»);
- ответ 1-6 слов и ДОСЛОВНО (с теми же падежами) содержится в тексте пункта: срок, число, название, термин;
- не спрашивай про номера пунктов и статей;
- если по пункту нельзя задать хороший вопрос с коротким ответом, верни {"skip": true}.

Верни только JSON: {"question": "...", "answer": "..."}

Документ: {doc}, {section}
Пункт: {text}"""


def ask(model, chunk):
    body = {"model": model, "temperature": 0, "messages": [{"role": "user", "content":
            PROMPT.replace("{doc}", chunk["doc"]).replace("{section}", str(chunk["section"])).replace("{text}", chunk["text"])}]}
    r = requests.post(URL, json=body, headers=HEADERS, timeout=120)
    r.raise_for_status()
    text = r.json()["choices"][0]["message"]["content"]
    return json.loads(re.search(r"\{.*\}", text, re.S).group(0))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=45)
    ap.add_argument("--model", default="anthropic/claude-sonnet-4.6")
    args = ap.parse_args()

    pool = [c for d in load_corpus() for c in chunk_structured(d) if 120 <= len(c["text"]) <= 900 and TOPIC.search(c["text"])]
    random.Random(0).shuffle(pool)
    out, kept = [], 0
    for chunk in pool:
        if kept >= args.n:
            break
        try:
            qa = ask(args.model, chunk)
        except Exception as e:
            print("ошибка:", e)
            continue
        if qa.get("skip") or not qa.get("answer"):
            continue
        if norm(qa["answer"]) not in norm(chunk["text"]):
            print("  ответа нет в цитате, пропуск:", qa["answer"])
            continue
        kept += 1
        out.append({"id": f"q-{kept}", "source": "corpus", "question": qa["question"], "answer": qa["answer"],
                    "evidence": chunk["text"], "doc": chunk["doc"], "section": chunk["section"],
                    "page": chunk.get("page", ""), "url": chunk["url"]})
        print(f"{kept:3d}. {qa['question']}  →  {qa['answer']}")
    Path(HERE / "data" / "questions_draft.jsonl").write_text(
        "\n".join(json.dumps(q, ensure_ascii=False) for q in out) + "\n", encoding="utf-8")
    print(f"\nсохранено {len(out)} в data/questions_draft.jsonl")
