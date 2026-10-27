"""Monta a pasta site/ (pronta para publicar como site estático) a partir do dashboard gerado.

Copia index.html e os arquivos de dados/mapas e gera a imagem de pré-visualização (og.png, 1200x630).
Uso: .venv/bin/python scripts/build_site.py   (rode scripts/build_dashboard.py antes)
"""
import argparse
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
DASH, SITE = ROOT / "dashboard", ROOT / "site"
ARQUIVOS = ["index.html", "geo_uf.js", "geo_mun.js", "dados_mun.js", "dados_local.js"]

ap = argparse.ArgumentParser()
ap.add_argument("--url", help="URL pública do site (sem barra final), para as tags og:image/og:url, ex.: https://usuario.github.io/eleicoes")
args = ap.parse_args()

SITE.mkdir(exist_ok=True)
for f in ARQUIVOS:
    shutil.copy2(DASH / f, SITE / f)
(SITE / ".nojekyll").write_text("")
if args.url:
    h = (SITE / "index.html").read_text()
    h = h.replace('content="og.png"', f'content="{args.url}/og.png"').replace('<meta property="og:type"', f'<meta property="og:url" content="{args.url}/">\n<meta property="og:type"', 1)
    (SITE / "index.html").write_text(h)

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1200, "height": 630})
    pg.goto((SITE / "index.html").as_uri())
    pg.wait_for_timeout(1000)
    pg.add_style_tag(content="""
      .top, footer, main > section:not(#mapa), .scope, #mapa h2, #mapa .sub, #mapa .card.s4, .mapbar, .glg, .ficha, #mapa .ins {display:none!important}
      body{padding:0} main{padding:0;max-width:none}
      #mapa .grid{display:block}
      #mapa .card.s8{position:fixed;inset:0;border:0;border-radius:0;padding:0;display:flex;align-items:center;gap:30px;background:var(--bg)}
      #og-t{flex:0 0 440px;padding-left:56px}
      #c-mapa{flex:1;height:630px;display:flex;align-items:center;justify-content:center}
      #c-mapa svg{max-height:600px;width:auto;max-width:100%}
    """)
    pg.evaluate("""() => {
      const c = document.querySelector('#mapa .card.s8'), t = document.createElement('div'); t.id = 'og-t';
      t.innerHTML = '<div style="font:700 56px/1.05 system-ui,sans-serif;letter-spacing:-.02em;color:#0b0b0b">Eleições 2026<br>em dados</div><div style="font:400 24px/1.35 system-ui,sans-serif;color:#52514e;margin-top:18px">2º turno: a prorrogação até as 19h, os votos nulos e o perfil das terceiras vias</div><div style="font:400 17px system-ui,sans-serif;color:#7a7974;margin-top:26px">Dados abertos do TSE</div>';
      c.insertBefore(t, c.firstChild);
      const f = document.createElement('div'); f.style.cssText = 'position:fixed;left:0;right:0;top:0;height:14px;background:var(--stripe);z-index:9'; document.body.appendChild(f);
    }""")
    pg.wait_for_timeout(300)
    pg.screenshot(path=str(SITE / "og.png"))
    b.close()

tam = sum(f.stat().st_size for f in SITE.iterdir() if f.is_file())
print(f"site/ pronto: {len(list(SITE.iterdir()))} arquivos, {tam / 1e6:.1f} MB")
