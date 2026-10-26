#!/bin/bash
# Etapa pós-coleta: espera as 28 UFs concluírem, baixa o log das seções que fecharam tarde
# (a ~40 req/s, bem abaixo do limite do TSE), regera o dashboard e exporta as imagens.
# Retomável: UFs de logs já baixados (tardias_<UF>.done) são puladas.
cd "$(dirname "$0")/.."
echo "$(date +%H:%M) aguardando a coleta principal..."
while [ "$(ls data/parquet/secao_2t_*.done 2>/dev/null | wc -l)" -lt 28 ]; do sleep 60; done
echo "$(date +%H:%M) coleta concluída; listando seções tardias"
.venv/bin/python -I scripts/lista_prorrogadas.py
for uf in $(cut -d, -f1 data/parquet/secoes_tardias.csv | tail -n +2 | sort -u); do
  [ -f data/parquet/tardias_$uf.done ] && continue
  echo "$(date +%H:%M) logs de $uf"
  .venv/bin/python -I scripts/fetch_votes_by_hour.py $uf --secoes data/parquet/secoes_tardias.csv --rps 40 --workers 32 2>&1 | tail -1 && touch data/parquet/tardias_$uf.done
done
echo "$(date +%H:%M) gerando dashboard e imagens"
.venv/bin/python scripts/build_dashboard.py | tail -1
.venv/bin/python scripts/export_cards.py | tail -2
echo "FIM $(date +%H:%M)"
