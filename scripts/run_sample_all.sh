#!/bin/bash
# amostra nacional (1 seção a cada 100) para detectar prorrogação por UF
cd "$(dirname "$0")/.."
for uf in AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO ZZ; do
  .venv/bin/python -I scripts/fetch_votes_by_hour.py $uf --every 100 2>&1 | tail -1
done
echo FIM
