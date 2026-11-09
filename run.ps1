Write-Host "=== 1. Instalando dependencias ==="
pip install -r requirements.txt

Write-Host "=== 2. Ingesta idempotente de datos ==="
python src/ingest.py

Write-Host "=== 3. Entrenamiento, Backtest y Forecast ==="
python src/train.py

Write-Host "=== 4. Iniciando Dashboard de Streamlit ==="
python -m streamlit run src/app.py