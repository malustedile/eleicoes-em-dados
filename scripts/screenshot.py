"""Tira print da página inteira do dashboard (claro e escuro) em out/."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
root = Path(__file__).resolve().parent.parent
with sync_playwright() as p:
    b = p.chromium.launch()
    for tema in ("light", "dark"):
        pg = b.new_page(viewport={"width": 1280, "height": 900}, color_scheme=tema)
        errs = []
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto((root / "dashboard/index.html").as_uri())
        pg.screenshot(path=str(root / f"out/dashboard_{tema}.png"), full_page=True)
        print(tema, "erros:", errs)
    b.close()
