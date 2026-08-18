#!/usr/bin/env bash
# Reset DB to a clean seeded state, then run gates. Usage: bash scripts/seed_reset.sh
set -e
cd "$(dirname "$0")/.."

echo "[seed_reset] Dropping application database..."
python3 - <<'PY'
import os
from pymongo import MongoClient
from dotenv import load_dotenv
load_dotenv('/app/backend/.env')
c = MongoClient(os.environ['MONGO_URL'])
c.drop_database(os.environ['DB_NAME'])
print('  dropped', os.environ['DB_NAME'])
PY

echo "[seed_reset] Restarting backend (re-seeds on startup)..."
sudo supervisorctl restart backend >/dev/null 2>&1 || true
# Seed Fase 28b/31/33 mengunggah foto contoh & membangkitkan jadwal: butuh lebih dari
# beberapa detik. Dulu skrip ini tidur 7s lalu langsung menjalankan gate, sehingga gate
# runtime gagal HANYA karena backend belum siap (bukan karena kode salah).
for i in $(seq 1 240); do
  if curl -sf http://localhost:8001/api/health >/dev/null 2>&1; then
    echo "  backend siap setelah ${i}s"
    break
  fi
  sleep 1
done
sleep 3

echo "[seed_reset] Running gates..."
bash scripts/run_all_gates.sh
echo "[seed_reset] DONE"
