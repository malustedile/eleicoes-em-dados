#!/bin/bash
# rodada nacional completa, retomável: pula UF cujo CSV já existe
cd "$(dirname "$0")/.."
for uf in AC AP RR RO TO SE AL DF MS ES RN PB PI MT AM GO MA PA CE SC PE PR RS BA RJ MG SP ZZ; do
  [ -f data/parquet/votes_by_hour_2t_$uf.done ] && continue
  .venv/bin/python -I scripts/fetch_votes_by_hour.py $uf --rps 50 --workers 96 2>&1 | tail -1 && touch data/parquet/votes_by_hour_2t_$uf.done
done
echo FIM
