"""Vigia o portal de dados abertos do TSE e baixa os boletins de urna web do 2º turno
(CSV por UF, com abertura/encerramento e votos por seção) assim que forem publicados.

Uso: python scripts/watch_tse_release.py [--intervalo 600] [--max-horas 72]
Saída: data/raw/bweb2t/*.zip
"""
import argparse, json, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "https://dadosabertos.tse.jus.br/api/3/action/package_show?id=resultados-2026-boletim-de-urna"

def segundo_turno():
    d = json.load(urllib.request.urlopen(urllib.request.Request(API, headers={"User-Agent": "analytics-eleicoes/1.0"}), timeout=60))
    return [r for r in d["result"]["resources"] if "segundo turno" in r["name"].lower() and r["url"].endswith(".zip")]

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--intervalo", type=int, default=600)
    ap.add_argument("--max-horas", type=float, default=72)
    a = ap.parse_args()
    fim = time.time() + a.max_horas * 3600
    out = ROOT / "data/raw/bweb2t"; out.mkdir(parents=True, exist_ok=True)
    while time.time() < fim:
        try:
            rs = segundo_turno()
        except Exception as e:
            print("erro ao consultar:", e, flush=True); rs = []
        if len(rs) >= 28:  # 26 UFs + DF + ZZ
            for r in rs:
                dest = out / r["url"].rsplit("/", 1)[1]
                if not dest.exists():
                    urllib.request.urlretrieve(r["url"], dest); print("baixado", dest.name, flush=True)
            print("FIM: boletins do 2º turno baixados", flush=True)
            break
        print(time.strftime("%H:%M"), f"2º turno ainda não publicado ({len(rs)} arquivos)", flush=True)
        time.sleep(a.intervalo)
