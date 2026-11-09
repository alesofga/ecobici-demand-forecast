#!/usr/bin/env bash
set -e

echo "=== 1. Instalando dependencias ==="
pip install -r requirements.txt

echo "=== 2. Ingesta idempotente de datos ==="
python src/ingest.py

echo "=== 3. Entrenamiento, Backtest y Forecast ==="
python src/train.py

echo "=== 4. Iniciando Dashboard de Streamlit ==="
python -m streamlit run src/app.py