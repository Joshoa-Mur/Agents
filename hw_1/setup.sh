#!/usr/bin/env bash
# Установка с чистого клона: окружение, ключ, ядро Jupyter, тесты.
#   ./setup.sh          — всё
# Дальше: .venv/bin/jupyter notebook ReAct_agent.ipynb → Kernel → Restart & Run All
set -euo pipefail
cd "$(dirname "$0")"

# 1. Окружение: uv по pyproject.toml + uv.lock, иначе обычный venv по requirements.txt
if command -v uv >/dev/null 2>&1; then
    uv sync
else
    python3 -m venv .venv
    .venv/bin/pip install -q -r requirements.txt
fi
PY=.venv/bin/python

# 2. Ключ: .env из шаблона, если его ещё нет
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Создан .env: впишите OPENROUTER_API_KEY и запустите скрипт ещё раз"
fi

# 3. Ядро Jupyter с тем именем, которое записано в ноутбуке
$PY -m ipykernel install --user --name react-agent-venv --display-name "Python (ReAct_Agent venv)" >/dev/null
echo "Ядро Jupyter: Python (ReAct_Agent venv)"

# 4. Тесты инструментов (web_search и page_find ходят в Википедию)
$PY -m pytest -v
