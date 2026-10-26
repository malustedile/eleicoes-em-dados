# Eleições 2026 em dados

Análise do 2º turno de 2026 a partir de dados abertos do TSE: a prorrogação da votação até as 19h, o que os
eleitores digitaram para anular o voto e o perfil das zonas onde cada terceira via foi votada. O resultado é um
site estático (`site/`), sem backend.

## Fontes
- **Arquivos de urna por seção** (`resultados.tse.jus.br`): boletim de urna (BU), registro digital do voto (RDV) e
  log de urna do 2º turno.
- **Dados abertos do TSE** (`dadosabertos.tse.jus.br`): votação por município/zona e perfil do eleitorado e do
  comparecimento (1º turno).
- **IBGE**: malhas dos estados e municípios.

## Como reproduzir
```bash
python3 -m venv .venv && .venv/bin/pip install duckdb pandas pyarrow playwright && .venv/bin/playwright install chromium
./scripts/run_full_secao.sh        # BU + RDV de todas as seções (horas; retomável; respeita o limite de 100 req/s do TSE)
./scripts/pos_coleta.sh            # logs das seções prorrogadas, dashboard e imagens
.venv/bin/python scripts/build_geo.py        # malhas (precisa de data/raw/geo; ver o script)
.venv/bin/python scripts/build_dashboard.py  # dashboard/index.html
.venv/bin/python scripts/build_site.py --url https://SEU-SITE   # pasta site/ para publicar
```
Os dados brutos (`data/`, vários GB) não ficam no repositório.

## Cuidados de leitura
- O voto é secreto. O registro digital do voto guarda o que foi digitado nos nulos, sem ligar ao eleitor.
- Idade, escolaridade e demais perfis só existem por **zona eleitoral**. As análises de perfil são **ecológicas**:
  descrevem zonas, não eleitores.
- Votos depois do prazo: exatos nas seções com log de urna; estimados nas demais por uma amostra de 1% das seções.
- Cor/raça foi declarada por só ~21% do eleitorado.

## Publicar
`site/` é um site estático. GitHub Pages: o workflow em `.github/workflows/pages.yml` publica a pasta
(Settings → Pages → Source: GitHub Actions). Vercel, Netlify e Cloudflare Pages também servem a pasta como está.
