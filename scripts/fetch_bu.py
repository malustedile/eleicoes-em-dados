"""Baixa o boletim de urna (bu.dat, ~1,5 KB) de cada seção do 2º turno e extrai:
abertura/encerramento, comparecimento e votos para presidente (candidato, branco, nulo).

Muito mais leve que o log (~160 KB). O encerramento permite achar as seções que ficaram
abertas além do horário e só então baixar o log delas (scripts/fetch_votes_by_hour.py --secoes).

Uso: python scripts/fetch_bu.py AC [--limit N] [--rps 40]
Saída: data/parquet/bu_2t_<UF>.csv (uma linha por seção)
"""
import argparse, csv, json, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ber import tlv                                                    # noqa: E402
from fetch_votes_by_hour import BASE, Limiter, get, sections, ROOT   # noqa: E402

def ints(v):
    return int.from_bytes(v, "big")

def parse_bu(raw):
    outer = next(tlv(raw))[3]
    inner = next(v for _, _, t, v in tlv(outer) if t == 4)
    root = next(tlv(inner))[3]
    res = {"abertura": "", "encerramento": "", "comparecimento": None, "pres": []}
    kids = list(tlv(root))
    for i, (cls, cons, tag, v) in enumerate(kids):
        if cls == 2 and tag == 0 and cons:
            ts = [x[3].decode() for x in tlv(v)]
            if len(ts) == 2:
                res["abertura"], res["encerramento"] = ts[0][9:15], ts[1][9:15]
        elif cls == 0 and tag == 2 and res["comparecimento"] is None and i > 4:
            res["comparecimento"] = ints(v)

    def walk(b):
        items = list(tlv(b))
        cargo = next((ints(x[3]) for x in items if x[0] == 2 and x[2] == 1 and not x[1]), None)
        lst = [x for x in items if x[0] == 0 and x[1] and x[2] == 16]
        entries = [e for _, _, _, c in lst for _, k, _, e in tlv(c) if k]
        votos = []
        for e in entries:
            f = {(c, t): (cons, val) for c, cons, t, val in tlv(e)}
            if (2, 1) in f and (2, 2) in f:
                num = None
                if (2, 3) in f:
                    ids = [ints(x[3]) for x in tlv(f[(2, 3)][1])]
                    num = ids[1] if len(ids) > 1 else None
                votos.append((ints(f[(2, 1)][1]), num, ints(f[(2, 2)][1])))
        if cargo == 1 and votos and not res["pres"]:
            res["pres"] = votos
        for _, cons, _, v in items:
            if cons:
                try: walk(v)
                except Exception: pass
    walk(root)
    return res

def one(args):
    uf, mun, nm, zona, sec, lim = args
    u = uf.lower()
    d = f"{BASE}/dados/{u}/{mun}/{zona}/{sec}"
    aux = get(f"{d}/p003221-{u}-m{mun}-z{zona}-s{sec}-aux.json", lim)
    if not aux:
        return None
    hs = json.loads(aux).get("hashes", [])
    if not hs:
        return None
    bu = get(f"{d}/{hs[-1]['hash']}/o03221{u}{mun}{zona}{sec}-bu.dat", lim)
    if not bu:
        return None
    try:
        r = parse_bu(bu)
    except Exception:
        return None
    vs = r["pres"]
    return {"uf": uf, "cd_municipio": mun, "municipio": nm, "zona": zona, "secao": sec,
            "abertura": r["abertura"], "encerramento": r["encerramento"], "comparecimento": r["comparecimento"],
            "pres_branco": sum(q for t, n, q in vs if t == 2), "pres_nulo": sum(q for t, n, q in vs if t == 3),
            "pres_nominais": ";".join(f"{n}:{q}" for t, n, q in vs if t == 1)}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("uf")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--rps", type=float, default=40)
    ap.add_argument("--workers", type=int, default=64)
    a = ap.parse_args()
    lim = Limiter(a.rps)
    out = ROOT / "data" / "parquet" / f"bu_2t_{a.uf.upper()}.csv"
    secs = [(a.uf, m, n, z, s, lim) for m, n, z, s in sections(a.uf, lim)]
    if a.limit:
        secs = secs[: a.limit]
    cols = ["uf", "cd_municipio", "municipio", "zona", "secao", "abertura", "encerramento", "comparecimento",
            "pres_branco", "pres_nulo", "pres_nominais"]
    ok = 0
    print(f"{a.uf}: {len(secs)} seções", file=sys.stderr)
    with open(out, "w", newline="") as f, ThreadPoolExecutor(a.workers) as ex:
        w = csv.DictWriter(f, cols); w.writeheader()
        for r in ex.map(one, secs):
            if r: w.writerow(r); ok += 1
    print(f"pronto: {ok}/{len(secs)} -> {out}", file=sys.stderr)
