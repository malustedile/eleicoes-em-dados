"""Baixa o RDV (registro digital do voto) de cada seção do 2º turno e agrega, por seção e cargo,
quantos votos cada tipo/dígito teve. O RDV não identifica o eleitor nem guarda a ordem do voto.

tipo: 2 = nominal (digitos = número do candidato), 3 = branco, 4 = nulo (digitos = o que foi digitado).
Cargos: 1 = Presidente, 3 = Governador.

Uso: python scripts/fetch_rdv.py AC [--limit N] [--rps 25]
Saída: data/parquet/rdv_2t_<UF>.csv (formato longo)
"""
import argparse, csv, json, sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ber import tlv                                                    # noqa: E402
from fetch_votes_by_hour import BASE, Limiter, get, sections, ROOT   # noqa: E402

def votos(x):
    out = []
    for cls, cons, t, v in tlv(x):
        if cons and (cls, t) == (0, 16):
            items = list(tlv(v))
            tipo = next((int.from_bytes(i[3], "big") for i in items if (i[0], i[2]) == (0, 10) and not i[1]), None)
            dig = next((i[3].decode() for i in items if (i[0], i[2]) == (0, 18)), "")
            out.append((tipo, dig))
    return out

def parse_rdv(raw):
    res = {}
    def walk(x):
        items = list(tlv(x))
        cargo = next((int.from_bytes(i[3], "big") for i in items if (i[0], i[2]) == (2, 1) and not i[1]), None)
        lst = [i for i in items if (i[0], i[2]) == (0, 16) and i[1]]
        if cargo is not None and lst:
            vs = []
            for _, _, _, v in lst:
                vs += votos(v)
            if vs and all(a is not None for a, _ in vs):
                res.setdefault(cargo, vs)
        for _, k, _, v in items:
            if k:
                walk(v)
    walk(raw)
    return res

def one(args):
    uf, mun, nm, zona, sec, lim = args
    u = uf.lower()
    d = f"{BASE}/dados/{u}/{mun}/{zona}/{sec}"
    aux = get(f"{d}/p003221-{u}-m{mun}-z{zona}-s{sec}-aux.json", lim)
    if not aux:
        return []
    hs = json.loads(aux).get("hashes", [])
    if not hs:
        return []
    rdv = get(f"{d}/{hs[-1]['hash']}/o03221{u}{mun}{zona}{sec}-rdv.dat", lim)
    if not rdv:
        return []
    try:
        res = parse_rdv(rdv)
    except Exception:
        return []
    rows = []
    for cargo, vs in res.items():
        for (tipo, dig), q in Counter(vs).items():
            rows.append([uf, mun, nm, zona, sec, cargo, tipo, dig, q])
    return rows

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("uf")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--every", type=int, default=1, help="amostra sistemática: 1 seção a cada K")
    ap.add_argument("--rps", type=float, default=25)
    ap.add_argument("--workers", type=int, default=24)
    a = ap.parse_args()
    lim = Limiter(a.rps)
    out = ROOT / "data" / "parquet" / f"rdv_2t_{a.uf.upper()}.csv"
    secs = [(a.uf, m, n, z, s, lim) for m, n, z, s in sections(a.uf, lim)]
    if a.every > 1:
        secs = secs[:: a.every]
    if a.limit:
        secs = secs[: a.limit]
    print(f"{a.uf}: {len(secs)} seções", file=sys.stderr)
    ok = 0
    with open(out, "w", newline="") as f, ThreadPoolExecutor(a.workers) as ex:
        w = csv.writer(f)
        w.writerow(["uf", "cd_municipio", "municipio", "zona", "secao", "cargo", "tipo", "digitos", "qtd"])
        for rows in ex.map(one, secs):
            if rows:
                w.writerows(rows); ok += 1
    print(f"pronto: {ok}/{len(secs)} -> {out}", file=sys.stderr)
