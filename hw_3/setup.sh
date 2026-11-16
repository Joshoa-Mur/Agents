#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
if [ ! -f .env ]; then
    cp .env.example .env
fi
