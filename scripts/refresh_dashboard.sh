#!/bin/bash
# Regera o dashboard quando uma UF conclui (confere a cada 60 s) e a cada 10 min (progresso e estimativa).
cd "$(dirname "$0")/.."
ultimo=-1; min=0
while true; do
  n=$(ls data/parquet/secao_2t_*.done 2>/dev/null | wc -l)
  if [ "$n" != "$ultimo" ] || [ "$min" -ge 10 ]; then
    echo "$(date +%H:%M) UFs concluídas: $n"
    .venv/bin/python scripts/build_dashboard.py 2>&1 | tail -1
    ultimo=$n; min=0
  fi
  [ "$n" -ge 28 ] && { echo "coleta completa: dashboard final gerado"; break; }
  sleep 60; min=$((min+1))
done
