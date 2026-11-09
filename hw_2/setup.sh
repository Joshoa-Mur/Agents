set -euo pipefail
cd "$(dirname "$0")"

# Окружение: uv по pyproject.toml + uv.lock
if command -v uv >/dev/null 2>&1; then
    uv sync
else
    python3 -m venv .venv
    .venv/bin/pip install -q -r requirements.txt
fi
PY=.venv/bin/python

# Ключ:
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Создан .env: впишите OPENROUTER_API_KEY"
fi

#  Milvus поднимаем
docker compose up -d
echo -n "Жду Milvus"
for _ in $(seq 60); do
    curl -sf http://localhost:9091/healthz >/dev/null && { echo " — готов"; break; }
    echo -n "."; sleep 2
done
curl -sf http://localhost:9091/healthz >/dev/null || { echo " — не поднялся, см. docker compose logs"; exit 1; }

# Корпус: уже лежит в репо; скачать заново, только если его нет
[ -f data/corpus.jsonl ] || $PY fetch_corpus.py
echo "Корпус: $(wc -l < data/corpus.jsonl) документов"
