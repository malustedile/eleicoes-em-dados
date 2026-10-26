"""Lista as seções que fecharam 30 min ou mais depois do prazo (onde pode haver votos depois do horário).

O prazo de cada município é a hora de abertura mais frequente + 9h (8h às 17h de Brasília, ajustado ao fuso).
Saída: data/parquet/secoes_tardias.csv (uf, cd_municipio, zona, secao, atraso), usada por fetch_votes_by_hour.py --secoes.
"""
import csv
import sys
from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parent.parent
PQ = ROOT / "data" / "parquet"
files = sorted(str(f) for f in PQ.glob("bu_2t_*.csv"))
c = duckdb.connect()
c.execute(f"""create table bu as select * from read_csv({files!r}, union_by_name=true, ignore_errors=true,
    types={{'cd_municipio':'VARCHAR','zona':'VARCHAR','secao':'VARCHAR','abertura':'VARCHAR','encerramento':'VARCHAR'}})""")
c.execute("""create table b as select uf, cd_municipio, zona, secao, cast(substr(abertura,1,2) as int) ah,
    cast(substr(encerramento,1,2) as int)*60 + cast(substr(encerramento,3,2) as int) enc
    from bu where length(abertura)=6 and length(encerramento)=6 and uf <> 'ZZ'""")
c.execute("create table off as select uf, cd_municipio, mode(ah) mah from b group by 1,2")
rows = c.execute("""select b.uf, b.cd_municipio, b.zona, b.secao, b.enc - (o.mah+9)*60 atraso
    from b join off o using (uf, cd_municipio) where b.enc - (o.mah+9)*60 >= 30 order by 1,2,3,4""").fetchall()
out = PQ / "secoes_tardias.csv"
with open(out, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["uf", "cd_municipio", "zona", "secao", "atraso"])
    w.writerows(rows)
por_uf = {}
for r in rows:
    por_uf[r[0]] = por_uf.get(r[0], 0) + 1
print(f"{len(rows)} seções tardias em {len(por_uf)} UFs -> {out}", file=sys.stderr)
print(", ".join(f"{u}:{n}" for u, n in sorted(por_uf.items(), key=lambda x: -x[1])), file=sys.stderr)
