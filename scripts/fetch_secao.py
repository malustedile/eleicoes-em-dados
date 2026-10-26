"""Coleta completa do 2º turno por seção, numa passada: ficha (aux) + BU + RDV.

BU  -> data/parquet/bu_2t_<UF>.csv       (abertura, encerramento, comparecimento, votos presidente)
RDV -> data/parquet/rdvfull_2t_<UF>.csv  (formato longo: seção, cargo, tipo, dígitos, qtd)

Retomável por seção: seções já presentes no CSV de BU são puladas. O BU é escrito por último,
então ele marca a seção como concluída; na leitura, deduplique o RDV por (seção, cargo, tipo, dígitos).

Uso: python scripts/fetch_secao.py SP [--limit N] [--rps 60] [--workers 48]
"""
import argparse, csv, json, sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_votes_by_hour import BASE, Limiter, get, sections, ROOT   # noqa: E402
from fetch_bu import parse_bu                                         # noqa: E402
from fetch_rdv import parse_rdv                                       # noqa: E402

BU_COLS = ["uf", "cd_municipio", "municipio", "zona", "secao", "abertura", "encerramento", "comparecimento",
           "pres_branco", "pres_nulo", "pres_nominais"]
RDV_COLS = ["uf", "cd_municipio", "municipio", "zona", "secao", "cargo", "tipo", "digitos", "qtd"]

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
    base = f"{d}/{hs[-1]['hash']}/o03221{u}{mun}{zona}{sec}"
    bu, rdv = get(f"{base}-bu.dat", lim), get(f"{base}-rdv.dat", lim)
    if not bu or not rdv:
        return None
    try:
        b, r = parse_bu(bu), parse_rdv(rdv)
    except Exception:
        return None
    vs = b["pres"]
    bu_row = [uf, mun, nm, zona, sec, b["abertura"], b["encerramento"], b["comparecimento"],
              sum(q for t, n, q in vs if t == 2), sum(q for t, n, q in vs if t == 3),
              ";".join(f"{n}:{q}" for t, n, q in vs if t == 1)]
    rdv_rows = [[uf, mun, nm, zona, sec, cargo, tipo, dig, q]
                for cargo, v in r.items() for (tipo, dig), q in Counter(v).items()]
    return bu_row, rdv_rows

def feitas(path):
    if not path.exists():
        return set()
    with open(path, newline="") as f:
        rd = csv.reader(f)
        next(rd, None)
        return {(r[1], r[3], r[4]) for r in rd if len(r) == len(BU_COLS)}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("uf")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--rps", type=float, default=60)
    ap.add_argument("--workers", type=int, default=48)
    a = ap.parse_args()
    lim = Limiter(a.rps)
    out = ROOT / "data" / "parquet"
    fbu, frdv = out / f"bu_2t_{a.uf.upper()}.csv", out / f"rdvfull_2t_{a.uf.upper()}.csv"
    ja = feitas(fbu)
    secs = [(a.uf, m, n, z, s, lim) for m, n, z, s in sections(a.uf, lim) if (m, z, s) not in ja]
    if a.limit:
        secs = secs[: a.limit]
    print(f"{a.uf}: {len(secs)} seções a coletar ({len(ja)} já feitas)", file=sys.stderr, flush=True)
    novo = not ja
    ok = 0
    with open(fbu, "w" if novo else "a", newline="") as f1, open(frdv, "w" if novo else "a", newline="") as f2, \
            ThreadPoolExecutor(a.workers) as ex:
        w1, w2 = csv.writer(f1), csv.writer(f2)
        if novo:
            w1.writerow(BU_COLS); w2.writerow(RDV_COLS)
        for i, res in enumerate(ex.map(one, secs), 1):
            if res:
                w2.writerows(res[1]); w1.writerow(res[0]); ok += 1
            if i % 500 == 0:
                f1.flush(); f2.flush()
                print(f"  {a.uf} {i}/{len(secs)} (ok={ok})", file=sys.stderr, flush=True)
    print(f"pronto: {a.uf} {ok}/{len(secs)} -> {fbu.name}, {frdv.name}", file=sys.stderr, flush=True)
