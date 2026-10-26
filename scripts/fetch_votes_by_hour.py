"""Baixa o log de urna (log.jez) de cada seção do 2º turno e extrai a hora de cada
voto computado. Não guarda o log, só o horário de cada voto (sem identificar eleitor).

Uso: python scripts/fetch_votes_by_hour.py AC [--limit N] [--rps 15]
Saída: data/parquet/votes_by_hour_2t_<UF>.csv (uma linha por seção)
"""
import argparse, csv, io, json, re, sys, time, threading, zipfile
import http.client, urllib.request, urllib.error
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3221"
DIA = "25/10/2026"

class Limiter:
    def __init__(self, rps):
        self.gap, self.next, self.lock = 1 / rps, 0.0, threading.Lock()
    def wait(self):
        with self.lock:
            now = time.monotonic()
            t = max(now, self.next)
            self.next = t + self.gap
        if t > now:
            time.sleep(t - now)

HOST = "resultados.tse.jus.br"
_tl = threading.local()          # uma conexão HTTPS persistente por thread (evita o custo do TLS a cada requisição)
_pause = {"ate": 0.0}
_pause_lock = threading.Lock()

def get(url, lim, tries=4):
    path = url.split(HOST, 1)[1]
    for i in range(tries):
        espera = _pause["ate"] - time.monotonic()
        if espera > 0:
            time.sleep(espera)
        lim.wait()
        try:
            c = getattr(_tl, "c", None)
            if c is None:
                c = _tl.c = http.client.HTTPSConnection(HOST, timeout=60)
            c.request("GET", path, headers={"User-Agent": "analytics-eleicoes/1.0"})
            r = c.getresponse()
            body = r.read()
            if r.status == 200:
                return body
            if r.status == 404:
                return None  # não insistir: 404 em excesso bloqueia o IP
            if r.status in (403, 429):  # provável bloqueio do TSE (dura 10 min): todas as threads pausam
                with _pause_lock:
                    _pause["ate"] = max(_pause["ate"], time.monotonic() + 660)
                print(f"HTTP {r.status}: possível bloqueio, pausando 11 min", file=sys.stderr, flush=True)
                continue
            time.sleep(2 * (i + 1))
        except Exception:
            _tl.c = None
            time.sleep(2 * (i + 1))
    return None

def sections(uf, lim):
    cfg = json.loads(get(f"{BASE}/config/{uf.lower()}/{uf.lower()}-p003221-cs.json", lim))
    for abr in cfg["abr"]:
        for mu in abr["mu"]:
            for z in mu["zon"]:
                for s in z["sec"]:
                    yield mu["cd"], mu["nm"], z["cd"], s["ns"]

def one(args):
    uf, mun, nm, zona, sec, lim = args
    u = uf.lower()
    d = f"{BASE}/dados/{u}/{mun}/{zona}/{sec}"
    aux = get(f"{d}/p003221-{u}-m{mun}-z{zona}-s{sec}-aux.json", lim)
    if not aux:
        return None
    hashes = json.loads(aux).get("hashes", [])
    if not hashes:
        return None
    h = hashes[-1]["hash"]
    log = get(f"{d}/{h}/o03221{u}{mun}{zona}{sec}-log.jez", lim)
    if not log:
        return None
    try:
        txt = zipfile.ZipFile(io.BytesIO(log)).read("logd.dat").decode("latin1")
    except Exception:
        return None
    horas, encerr = [], ""
    for line in txt.splitlines():
        if not line.startswith(DIA):
            continue
        if "O voto do eleitor foi computado" in line:
            horas.append(line[11:19])
        elif "Operador selecionou: Encerrar votação" in line:
            encerr = line[11:19]
    if not horas:
        return None
    por_hora = Counter(int(x[:2]) for x in horas)
    # votos a cada 15 min, das 15h às 20h45 (hora local da urna): mostra o fim da votação e a prorrogação
    por_q = Counter((int(x[:2]), (int(x[3:5]) // 15) * 15) for x in horas if int(x[:2]) >= 15)
    row = {"uf": uf, "cd_municipio": mun, "municipio": nm, "zona": zona, "secao": sec,
           "votos": len(horas), "primeiro_voto": min(horas), "ultimo_voto": max(horas), "encerramento": encerr}
    for hh in range(7, 24):
        row[f"h{hh:02d}"] = por_hora.get(hh, 0)
    for hh in range(15, 21):
        for mm in (0, 15, 30, 45):
            row[f"q{hh:02d}{mm:02d}"] = por_q.get((hh, mm), 0)
    return row

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("uf")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--every", type=int, default=1, help="amostra: 1 seção a cada K")
    ap.add_argument("--secoes", help="CSV com as seções a baixar (colunas uf,cd_municipio,zona,secao)")
    ap.add_argument("--rps", type=float, default=15)
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args()
    lim = Limiter(a.rps)
    suf = "_tardias" if a.secoes else (f"_amostra{a.every}" if a.every > 1 else "")
    out = ROOT / "data" / "parquet" / f"votes_by_hour_2t_{a.uf.upper()}{suf}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    secs = [(a.uf, m, n, z, s, lim) for m, n, z, s in sections(a.uf, lim)]
    if a.secoes:  # só as seções listadas (CSV com cd_municipio,zona,secao), ex.: as que fecharam tarde
        with open(a.secoes) as f:
            alvo = {(r["cd_municipio"], r["zona"], r["secao"]) for r in csv.DictReader(f) if r["uf"] == a.uf.upper()}
        secs = [x for x in secs if (x[1], x[3], x[4]) in alvo]
    if a.every > 1:
        secs = secs[:: a.every]
    if a.limit:
        secs = secs[: a.limit]
    print(f"{a.uf}: {len(secs)} seções", file=sys.stderr)
    cols = ["uf", "cd_municipio", "municipio", "zona", "secao", "votos", "primeiro_voto", "ultimo_voto", "encerramento"] + [f"h{h:02d}" for h in range(7, 24)] + [f"q{hh:02d}{mm:02d}" for hh in range(15, 21) for mm in (0, 15, 30, 45)]
    ok = 0
    with open(out, "w", newline="") as f, ThreadPoolExecutor(a.workers) as ex:
        w = csv.DictWriter(f, cols)
        w.writeheader()
        for i, r in enumerate(ex.map(one, secs), 1):
            if r:
                w.writerow(r); ok += 1
            if i % 200 == 0:
                print(f"  {i}/{len(secs)} (ok={ok})", file=sys.stderr)
    print(f"pronto: {ok}/{len(secs)} -> {out}", file=sys.stderr)
