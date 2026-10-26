"""Gera dashboard/geo_uf.js e dashboard/geo_mun.js a partir das malhas do IBGE (data/raw/geo).

Projeção equirretangular com correção de latitude, coordenadas arredondadas a 0,1 unidade, simplificação
Douglas-Peucker e caminhos SVG relativos. Também grava a correspondência código TSE -> código IBGE.

Uso: python scripts/build_geo.py
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "geo"
OUT = ROOT / "dashboard"
UF = {"11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO", "21": "MA", "22": "PI", "23": "CE", "24": "RN",
      "25": "PB", "26": "PE", "27": "AL", "28": "SE", "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR", "42": "SC",
      "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF"}
LON0, LAT0, LAT_MAX, S = -74.2, 5.4, 5.4, 16.0
K = math.cos(math.radians(15))

def proj(lon, lat):
    return ((lon - LON0) * K * S, (LAT0 - lat) * S)

def dp(pts, tol):
    """Douglas-Peucker iterativo sobre uma lista de (x, y)."""
    if len(pts) < 4:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    pilha = [(0, len(pts) - 1)]
    while pilha:
        a, b = pilha.pop()
        (x1, y1), (x2, y2) = pts[a], pts[b]
        dx, dy = x2 - x1, y2 - y1
        n = math.hypot(dx, dy) or 1e-9
        dmax, im = 0.0, -1
        for i in range(a + 1, b):
            d = abs(dy * (pts[i][0] - x1) - dx * (pts[i][1] - y1)) / n
            if d > dmax:
                dmax, im = d, i
        if dmax > tol and im > 0:
            keep[im] = True
            pilha += [(a, im), (im, b)]
    return [p for p, k in zip(pts, keep) if k]

def num(i):
    """Inteiro em décimos -> texto compacto (ex.: -5 -> '-.5', 123 -> '12.3', 20 -> '2')."""
    s = "-" if i < 0 else ""
    a = str(abs(i)).rjust(2, "0")
    int_, dec = a[:-1], a[-1]
    int_ = "" if int_ == "0" else int_
    return s + int_ + ("." + dec if dec != "0" else "") if (int_ or dec != "0") else "0"

def anel(coords, tol):
    pts = [proj(lon, lat) for lon, lat in coords]
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    tamanho = max(max(xs) - min(xs), max(ys) - min(ys))
    t = min(tol, tamanho * 0.12)           # anéis pequenos (municípios minúsculos) mantêm o formato
    # anel fechado: divide no ponto mais distante do primeiro e simplifica as duas metades
    m = max(range(len(pts)), key=lambda i: (pts[i][0] - pts[0][0]) ** 2 + (pts[i][1] - pts[0][1]) ** 2)
    sp = dp(pts[:m + 1], t)[:-1] + dp(pts[m:] + [pts[0]], t)[:-1]
    if len(sp) < 3:
        sp = pts[:3] if len(pts) >= 3 else pts
    q = [(round(x * 10), round(y * 10)) for x, y in sp]
    d = [q[0]]
    for p in q[1:]:
        if p != d[-1]:
            d.append(p)
    if len(d) < 3:
        return "", None
    rel = []
    for (x0, y0), (x1, y1) in zip(d, d[1:]):
        rel += [num(x1 - x0), num(y1 - y0)]
    return f"M{num(d[0][0])} {num(d[0][1])}l" + " ".join(rel) + "z", (sum(xs) / len(xs), sum(ys) / len(ys), tamanho)

def caminho(geom, tol):
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    partes, maior = [], (0, None)
    for poly in polys:
        for j, r in enumerate(poly):
            d, info = anel(r, tol)
            if d:
                partes.append(d)
                if j == 0 and info and info[2] > maior[0]:
                    maior = (info[2], info)
    return "".join(partes), maior[1]

def main():
    # --- estados ---
    uf = json.loads((RAW / "malha_UF.json").read_text())
    paths, rot = {}, {}
    for f in uf["features"]:
        sg = UF[f["properties"]["codarea"]]
        paths[sg], info = caminho(f["geometry"], 0.25)
        rot[sg] = [round(info[0], 1), round(info[1], 1)]
    W = round(max(proj(-34.7, 0)[0], 0) + 4, 1)
    H = round(proj(-60, -33.8)[1] + 4, 1)
    (OUT / "geo_uf.js").write_text("const GEO_UF=" + json.dumps({"w": W, "h": H, "p": paths, "c": rot}, separators=(",", ":"), ensure_ascii=False) + ";\n")
    # --- municípios ---
    mu = json.loads((RAW / "malha_municipio.json").read_text())
    cfg = json.loads((RAW / "tse_mun_cfg.json").read_text())
    nomes, tse2ibge = {}, {}
    for a in cfg["abr"]:
        for m in a["mu"]:
            if m.get("cdi") and m["cdi"].isdigit() and a["cd"] != "zz":
                nomes[m["cdi"]] = [m["nm"].title().replace(" De ", " de ").replace(" Do ", " do ").replace(" Da ", " da ").replace(" Dos ", " dos ").replace(" Das ", " das "), a["cd"].upper()]
                tse2ibge[m["cd"]] = m["cdi"]
    mp = {}
    for f in mu["features"]:
        mp[f["properties"]["codarea"]] = caminho(f["geometry"], 0.28)[0]
    (OUT / "geo_mun.js").write_text("const GEO_MUN=" + json.dumps({"p": mp, "n": nomes}, separators=(",", ":"), ensure_ascii=False) + ";\n")
    (ROOT / "out" / "tse2ibge.json").write_text(json.dumps(tse2ibge))
    print(f"UF: {len(paths)} | municípios: {len(mp)} | mapeados TSE->IBGE: {len(tse2ibge)} | viewBox {W}x{H}")
    for n in ("geo_uf.js", "geo_mun.js"):
        print(n, round((OUT / n).stat().st_size / 1024), "KB")

if __name__ == "__main__":
    main()
