"""Exporta cada gráfico (card) do dashboard como PNG em alta resolução, nos temas claro e escuro.

Uso: .venv/bin/python scripts/export_cards.py        -> out/cards/<tema>/NN_titulo.png
"""
import re
import unicodedata
from pathlib import Path
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parent.parent

def slug(t):
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:60]

with sync_playwright() as p:
    b = p.chromium.launch()
    for tema in ("light", "dark"):
        pg = b.new_page(viewport={"width": 1280, "height": 900}, device_scale_factor=2, color_scheme=tema)
        pg.goto((root / "dashboard/index.html").as_uri())
        pg.wait_for_timeout(800)
        pg.add_style_tag(content=".top{display:none!important}")
        out = root / "out" / "cards" / tema
        out.mkdir(parents=True, exist_ok=True)
        for f in out.glob("*.png"):
            f.unlink()
        cards = pg.locator(".card")
        n = 0
        for i in range(cards.count()):
            c = cards.nth(i)
            h = c.locator("h3").first
            if not c.is_visible() or "kpi" in (c.get_attribute("class") or ""):
                continue
            titulo = h.inner_text() if h.count() else ("mapa-por-uf-e-municipio" if c.locator("#c-mapa").count() else f"card-{i}")
            n += 1
            c.screenshot(path=str(out / f"{n:02d}_{slug(titulo)}.png"))
        print(tema, n, "imagens em", out)
    b.close()
