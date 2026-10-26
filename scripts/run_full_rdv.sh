#!/bin/bash
# RDV do 2º turno (inclui os dígitos digitados nos votos nulos), retomável
cd "$(dirname "$0")/.."
for uf in SP RJ MG BA RS PR PE CE PA MA GO SC PB ES PI AM RN AL MT DF MS SE RO TO AC AP RR ZZ; do
  [ -f data/parquet/rdv_2t_$uf.done ] && continue
  .venv/bin/python -I scripts/fetch_rdv.py $uf --every 20 --rps 40 --workers 32 2>&1 | tail -1 && touch data/parquet/rdv_2t_$uf.done
done
echo FIM
