"""Carrossel do LinkedIn sobre os votos nulos do 2º turno: PDF (1080x1350 por slide) e PNGs, a partir de dashboard/dados.json.

Uso: .venv/bin/python scripts/build_carrossel.py   -> out/carrossel/nulos_carrossel.pdf e slide_N.png
"""
import json
import re
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out" / "carrossel"
OUT.mkdir(parents=True, exist_ok=True)
D = json.loads((ROOT / "dashboard" / "dados.json").read_text())
GEO = json.loads(re.search(r"=(\{.*\});", (ROOT / "dashboard" / "geo_uf.js").read_text(), re.S).group(1))

def br(n, d=0):
    return f"{n:,.{d}f}".replace(",", "§").replace(".", ",").replace("§", ".")

T = D["totais"][0]
CLS = {r["classe"]: r for r in D["nulos_classes"]["pres"]}
zero, outro = CLS["Zeros (00)"], CLS["Outro número inexistente"]
elim, gov = CLS["Candidato eliminado no 1º turno"], CLS["Número de candidato a governador"]
DIG = D["nulos_digitos"]["pres"][:8]
ELIM = {k: v.split(" (")[0] for k, v in D["elim"].items()}
MAPA = {u: v for u, v in D["mapa"]["nulos"].items() if u != "ZZ"}
RANK = sorted(MAPA.items(), key=lambda x: -x[1])
secoes = D["coleta"]["secoes_ok"]
d14 = next(r["qtd"] for r in D["nulos_digitos"]["pres"] if r["digitos"] == "14")

def barras(itens, cor, maxv=None):
    maxv = maxv or max(v for _, v, _ in itens)
    linhas = []
    for rot, v, txt in itens:
        w = 100 * v / maxv * 0.78
        linhas.append(f'<div class="row"><div class="lab">{rot}</div><div class="bar"><i style="width:{w:.1f}%;background:{cor}"></i><b>{txt}</b></div></div>')
    return "\n".join(linhas)

def mapa_svg():
    xs = [v for v in MAPA.values()]
    lo, hi = min(xs), max(xs)
    ps = []
    for uf, d in GEO["p"].items():
        v = MAPA.get(uf)
        a = 0.12 + 0.88 * ((v - lo) / (hi - lo)) if v is not None else 0
        ps.append(f'<path d="{d}" style="fill:color-mix(in srgb,#2a78d6 {a * 100:.0f}%,#ffffff);stroke:#f3f2ee;stroke-width:1.4;stroke-linejoin:round"/>')
    tx = []
    for uf, (x, y) in GEO["c"].items():
        if uf in ("DF",) or uf not in MAPA:
            continue
        a = (MAPA[uf] - lo) / (hi - lo)
        tx.append(f'<text x="{x}" y="{y + 4}" text-anchor="middle" style="font:700 12px DejaVu Sans,sans-serif;fill:{"#fff" if a > .5 else "#0b0b0b"}">{uf}</text>')
    return f'<svg viewBox="0 0 {GEO["w"]} {GEO["h"]}" style="width:100%;height:auto">{"".join(ps)}{"".join(tx)}</svg>', lo, hi

mapa, lo, hi = mapa_svg()
topo = "".join(f'<li><b>{u}</b><span>{br(v, 1)}%</span></li>' for u, v in RANK[:4])
base = "".join(f'<li><b>{u}</b><span>{br(v, 1)}%</span></li>' for u, v in RANK[::-1][:4][::-1])

CSS = """
@page{size:1080px 1350px;margin:0}
*{box-sizing:border-box}
html,body{margin:0;background:#f3f2ee;font-family:"DejaVu Sans",system-ui,sans-serif;color:#0b0b0b}
.s{width:1080px;height:1350px;position:relative;padding:90px 90px 120px;background:#f3f2ee;page-break-after:always;overflow:hidden;display:flex;flex-direction:column}
.tag{font-size:24px;letter-spacing:.14em;text-transform:uppercase;color:#7a7974;margin-bottom:34px;font-weight:700}
h1{font-size:92px;line-height:1.04;margin:0;letter-spacing:-.025em}
h2{font-size:62px;line-height:1.1;margin:0 0 20px;letter-spacing:-.02em}
p{font-size:38px;line-height:1.4;color:#52514e;margin:0 0 24px}
.rod{position:absolute;left:90px;right:90px;bottom:54px;display:flex;justify-content:space-between;font-size:22px;color:#7a7974}
.dark{background:#0e1e33;color:#fff}.dark .tag{color:#7fa8de}.dark p{color:#c9d6e8}.dark .rod{color:#7fa8de}
.big{font-size:150px;font-weight:700;letter-spacing:-.03em;line-height:1}
.kv{display:flex;gap:40px;margin-top:40px}.kv>div{flex:1;background:#fcfcfb;border:2px solid #e4e2dc;border-radius:22px;padding:34px}
.kv b{display:block;font-size:110px;letter-spacing:-.02em;line-height:1.05}.kv span{font-size:28px;color:#52514e}
.row{display:flex;align-items:center;margin:22px 0}
.lab{flex:0 0 330px;font-size:31px;color:#0b0b0b;line-height:1.2;padding-right:20px}
.bar{flex:1;display:flex;align-items:center;gap:18px}
.bar i{display:block;height:58px;border-radius:12px}.bar b{font-size:36px;white-space:nowrap}
.dens .row{margin:12px 0}.dens .bar i{height:50px}.dens .lab{font-size:30px}
.urna{display:flex;gap:26px;margin-top:70px}.urna span{width:150px;height:190px;border:6px solid #2a78d6;border-radius:26px;display:flex;align-items:center;justify-content:center;font-size:120px;font-weight:700;color:#7fa8de}
.nota{font-size:27px;color:#7a7974;margin-top:auto}
.mapa{display:flex;gap:34px;align-items:center;margin-top:10px}.mapa .m{flex:0 0 620px}
.lst{flex:1}.lst h4{font-size:26px;margin:0 0 10px;color:#7a7974;text-transform:uppercase;letter-spacing:.1em}
.lst ul{list-style:none;margin:0 0 30px;padding:0}.lst li{display:flex;justify-content:space-between;font-size:36px;padding:10px 0;border-bottom:2px solid #e4e2dc}
.lst li b{font-weight:700}
.cta{margin-top:50px;background:#2a78d6;color:#fff;border-radius:22px;padding:44px 48px;font-size:42px;line-height:1.35}
ul.pts{margin:0;padding-left:44px}.pts li{font-size:40px;line-height:1.4;color:#52514e;margin:0 0 22px}
.leg{display:flex;align-items:center;gap:14px;font-size:24px;color:#52514e;margin-top:6px}.grad{flex:1;height:14px;border-radius:99px;background:linear-gradient(90deg,#d8e6f8,#2a78d6)}
"""

def rod(n):
    return f'<div class="rod"><span>Eleições 2026 em dados · dados abertos do TSE</span><span>{n}/6</span></div>'

slides = []
slides.append(f'''<div class="s dark"><div class="tag">Eleições 2026 · 2º turno</div>
<h1>{br(T["nulos"] / 1e6, 1)} milhões de brasileiros anularam o voto para presidente.</h1>
<p style="margin-top:50px;font-size:54px;color:#fff;line-height:1.2">O que eles digitaram na urna?</p>
<div class="urna"><span>?</span><span>?</span></div>
<p style="margin-top:auto;font-size:34px">Deslize →</p>{rod(1)}</div>''')

slides.append(f'''<div class="s"><div class="tag">Como dá para saber</div>
<h2>O voto é secreto. Mas o que se digita nos nulos fica registrado.</h2>
<p>O registro digital do voto guarda os números digitados em cada voto nulo. Ele não identifica o eleitor nem a ordem em que votou.</p>
<p>Li o arquivo de {br(secoes)} seções eleitorais do 2º turno.</p>
<div class="kv"><div><b>{br(100 * T["nulos"] / T["total"], 1)}%</b><span>dos votos para presidente foram nulos</span></div><div><b>{br(100 * T["brancos"] / T["total"], 1)}%</b><span>foram em branco</span></div></div>{rod(2)}</div>''')

itens = [("Digitaram 00", zero["pct"], f'{br(zero["pct"], 1)}%'), ("Outro número que não existe", outro["pct"], f'{br(outro["pct"], 1)}%'),
         ("Número de candidato eliminado no 1º turno", elim["pct"], f'{br(elim["pct"], 1)}%'), ("Número de candidato a governador", gov["pct"], f'{br(gov["pct"], 1)}%')]
slides.append(f'''<div class="s"><div class="tag">O que foi digitado</div>
<h2>Mais da metade digitou 00.</h2>
<p>Tipo de número digitado nos votos nulos para presidente.</p>
{barras(itens, "#2a78d6", 100)}
<div class="nota">% dos {br(T["nulos"])} votos nulos para presidente. No 2º turno só havia dois candidatos: 13 e 22.</div>{rod(3)}</div>''')

ditens = []
for r in DIG[:7]:
    rot = r["digitos"] + (f' · {ELIM[r["digitos"]]}' if r["digitos"] in ELIM else "")
    q = r["qtd"]
    ditens.append((rot, q, f'{br(q / 1e6, 2)} mi' if q >= 1e6 else f'{br(q / 1e3)} mil'))
slides.append(f'''<div class="s dens"><div class="tag">Os números mais digitados</div>
<h2>Quem foi eliminado ainda aparece na urna.</h2>
<p>{br(elim["pct"], 1)}% dos nulos foram o número de um candidato do 1º turno. O 14, de Renan Santos, apareceu {br(d14 / 1e3)} mil vezes.</p>
{barras(ditens, "#1baf7a")}
<div class="nota">Votos nulos para presidente por número digitado, 2º turno.</div>{rod(4)}</div>''')

slides.append(f'''<div class="s"><div class="tag">Onde mais se anulou</div>
<h2>De {br(RANK[0][1], 1)}% em {RANK[0][0]} a {br(RANK[-1][1], 1)}% em {RANK[-1][0]}.</h2>
<div class="mapa"><div class="m">{mapa}<div class="leg"><span>{br(lo, 1)}%</span><span class="grad"></span><span>{br(hi, 1)}%</span></div></div>
<div class="lst"><h4>Mais nulos</h4><ul>{topo}</ul><h4>Menos nulos</h4><ul>{base}</ul></div></div>
<div class="nota" style="margin-top:34px">% de votos nulos para presidente em cada UF.</div>{rod(5)}</div>''')

slides.append(f'''<div class="s dark"><div class="tag">Como ler</div>
<h2 style="color:#fff">O que esses números dizem, e o que não dizem.</h2>
<ul class="pts" style="margin-top:20px"><li style="color:#c9d6e8">00 é o jeito mais comum de anular de propósito. Os demais números podem ser protesto, erro ou engano: o dado não mostra a intenção.</li>
<li style="color:#c9d6e8">O registro não liga o número digitado a nenhum eleitor.</li>
<li style="color:#c9d6e8">Fonte: dados abertos do TSE. Análise independente.</li></ul>
<div class="cta">Mapa interativo por município e outras análises: link nos comentários.</div>{rod(6)}</div>''')

html = f"<!doctype html><html lang='pt-BR'><meta charset='utf-8'><style>{CSS}</style><body>{''.join(slides)}</body></html>"
(OUT / "carrossel.html").write_text(html)

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1080, "height": 1350})
    pg.goto((OUT / "carrossel.html").as_uri())
    pg.wait_for_timeout(500)
    for i, el in enumerate(pg.locator(".s").all(), 1):
        el.screenshot(path=str(OUT / f"slide_{i}.png"))
    pg.pdf(path=str(OUT / "nulos_carrossel.pdf"), width="1080px", height="1350px", print_background=True)
    b.close()
print("ok:", OUT / "nulos_carrossel.pdf")
