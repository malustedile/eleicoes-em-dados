#!/bin/bash
# Coleta completa do 2º turno (BU + RDV por seção), retomável; estados grandes primeiro.
# Teto de 90 req/s no total (limite do TSE: 100 req/s por IP).
cd "$(dirname "$0")/.."
for uf in SP MG RJ BA RS PR PE CE PA MA GO SC PB ES PI AM RN AL MT DF MS SE RO TO AC AP RR ZZ; do
  [ -f data/parquet/secao_2t_$uf.done ] && continue
  .venv/bin/python -I scripts/fetch_secao.py $uf --rps 95 --workers 80 2>&1 | grep -E "pronto|a coletar|HTTP" && touch data/parquet/secao_2t_$uf.done
done
echo FIM
