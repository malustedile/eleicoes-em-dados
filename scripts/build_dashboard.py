"""Gera dashboard/index.html a partir dos dados coletados. Pode rodar a qualquer momento:
usa só UFs com coleta concluída (secao_2t_<UF>.done) para não enviesar com estados pela metade.

Uso: .venv/bin/python scripts/build_dashboard.py
"""
import glob, json, os, re, sys, time
from datetime import datetime
from pathlib import Path
import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
import idade_vias

ROOT = Path(__file__).resolve().parent.parent
PQ = ROOT / "data" / "parquet"
OUT = ROOT / "dashboard"
OUT.mkdir(exist_ok=True)
TOTAL_UFS = 28  # 26 UFs + DF + exterior (ZZ)
c = duckdb.connect()

def done(prefix):
    return sorted(re.search(r"_([A-Z]{2})\.done$", p).group(1) for p in glob.glob(str(PQ / f"{prefix}_*.done")))

TIPOS_BU = "types={'cd_municipio':'VARCHAR','zona':'VARCHAR','secao':'VARCHAR','abertura':'VARCHAR','encerramento':'VARCHAR'}"
TIPOS = "types={'cd_municipio':'VARCHAR','zona':'VARCHAR','secao':'VARCHAR','digitos':'VARCHAR'}"  # RDV
def lista(fs): return "[" + ",".join(repr(str(f)) for f in fs) + "]"

data = {"gerado": datetime.now().strftime("%d/%m/%Y %H:%M"), "total_ufs": TOTAL_UFS}

# ---------- coleta (progresso) ----------
tot_uf = json.loads((ROOT / "out/secoes_por_uf.json").read_text()) if (ROOT / "out/secoes_por_uf.json").exists() else {}
ufs_ok = [u for u in done("secao_2t") if u in tot_uf or True]
bu_files = sorted(PQ.glob("bu_2t_*.csv"))
secoes_ok = 0
if bu_files:
    c.execute(f"create table bu as select * from read_csv({lista(bu_files)}, union_by_name=true, ignore_errors=true, {TIPOS_BU})")
    secoes_ok = c.execute("select count(*) from bu").fetchone()[0]
ORDEM = "SP MG RJ BA RS PR PE CE PA MA GO SC PB ES PI AM RN AL MT DF MS SE RO TO AC AP RR ZZ".split()  # ordem da coleta
cont = dict(c.execute("select uf, count(*) from bu group by uf").fetchall()) if bu_files else {}
agora = time.time()
mtime = {p.stem[-2:]: p.stat().st_mtime for p in bu_files}
por_uf = []
for u in ORDEM:
    if u in ufs_ok:
        estado = "concluida"
    elif u in mtime and agora - mtime[u] < 600:   # arquivo atualizado nos últimos 10 min = coletando agora
        estado = "andamento"
    else:
        estado = "fila"
    por_uf.append({"uf": u, "ok": int(cont.get(u, 0)) if estado != "fila" else 0, "total": tot_uf.get(u, 0), "estado": estado})

# estimativa de término a partir do histórico de execuções do gerador
hist_f = ROOT / "out" / "progress_hist.json"
try:
    hist = json.loads(hist_f.read_text())
except Exception:
    hist = []
if not hist or hist[-1][1] != secoes_ok:
    hist.append([agora, secoes_ok])
    hist = hist[-400:]
hist_f.write_text(json.dumps(hist))
rec = [h for h in hist if agora - h[0] <= 3 * 3600]
taxa, eta = None, None
if len(rec) >= 2 and rec[-1][0] - rec[0][0] >= 300:
    taxa = (rec[-1][1] - rec[0][1]) / (rec[-1][0] - rec[0][0])
    total_s = sum(tot_uf.values())
    if taxa > 1 and total_s and secoes_ok < total_s:
        eta = datetime.fromtimestamp(agora + (total_s - secoes_ok) / taxa).strftime("%H:%M")
data["coleta"] = {"secoes_ok": secoes_ok, "secoes_total": sum(tot_uf.values()) or None,
                  "ufs_concluidas": ufs_ok, "por_uf": por_uf, "taxa": round(taxa, 1) if taxa else None, "eta": eta}

# ---------- 1. prorrogação (boletim de urna: hora de encerramento de cada seção) ----------
# Prazo local de cada município = hora de abertura mais frequente + 9h (8h às 17h de Brasília, ajustado ao fuso).
if bu_files and ufs_ok:
    inc = ",".join(repr(u) for u in ufs_ok if u != "ZZ")
    c.execute(f"""create table bu2 as select *, cast(substr(abertura,1,2) as int) ah,
        cast(substr(encerramento,1,2) as int)*60 + cast(substr(encerramento,3,2) as int) enc
        from bu where length(encerramento)=6 and length(abertura)=6 and uf in ({inc})""")
    c.execute("create table off as select uf, cd_municipio, mode(ah) mah from bu2 group by 1,2")
    c.execute("""create table bu3 as select b.*, b.enc - (o.mah+9)*60 atraso from bu2 b join off o using (uf, cd_municipio)""")
    n, comp = c.execute("select count(*), sum(comparecimento) from bu3").fetchone()
    B = "case when atraso<30 then '1' when atraso<60 then '2' when atraso<105 then '3' else '4' end"
    nomes = {"1": "Até 30 min depois", "2": "30 a 60 min", "3": "1h a 1h45", "4": "Prorrogadas (1h45 ou mais)"}
    data["pror"] = {
        "ufs": [u for u in ufs_ok if u != "ZZ"], "secoes": int(n), "comparecimento": int(comp or 0),
        "buckets": [{"b": nomes[b], "secoes": int(s), "comp": int(cm or 0)} for b, s, cm in
                    c.execute(f"select {B} b, count(*), sum(comparecimento) from bu3 group by 1 order by 1").fetchall()],
        "por_uf": [dict(zip(["uf", "secoes", "n60", "n105", "comp105"], r)) for r in c.execute("""
            select uf, count(*), sum(case when atraso>=60 then 1 else 0 end), sum(case when atraso>=105 then 1 else 0 end),
                   coalesce(sum(case when atraso>=105 then comparecimento end),0)
            from bu3 group by 1 order by 4 desc""").fetchall()],
        "top_mun": [dict(zip(["uf", "municipio", "secoes", "n60", "n105"], r)) for r in c.execute("""
            select uf, municipio, count(*), sum(case when atraso>=60 then 1 else 0 end), sum(case when atraso>=105 then 1 else 0 end) n
            from bu3 group by uf, municipio order by n desc, 4 desc limit 12""").fetchall()],
    }
    data["pror"]["hist"] = [{"b": int(x), "n": int(n)} for x, n in c.execute(
        "select cast(floor(atraso/10)*10 as int) b, count(*) from bu3 where atraso >= 30 and atraso < 200 group by 1 order by 1").fetchall()]
    data["pror"]["tardias_fora"] = int(c.execute("select count(*) from bu3 where atraso >= 200").fetchone()[0])

    # ---- votos depois do prazo: log de urna das seções que fecharam tarde (exato) + estimativa para as demais (amostra de 1%) ----
    lf = sorted(PQ.glob(os.environ.get("TARDIAS_GLOB", "votes_by_hour_2t_*_tardias.csv")))
    # só usa os logs quando TODAS as UFs da lista de seções tardias terminaram (senão o número seria parcial)
    lista_t = PQ / "secoes_tardias.csv"
    if "TARDIAS_GLOB" not in os.environ:
        ufs_t = {l.split(",")[0] for l in lista_t.read_text().splitlines()[1:]} if lista_t.exists() else set()
        if not ufs_t or not all((PQ / f"tardias_{u}.done").exists() for u in ufs_t):
            lf = []
    TLOG = "types={'cd_municipio':'VARCHAR','zona':'VARCHAR','secao':'VARCHAR'}"
    if lf:
        c.execute(f"create or replace table lt as select * from read_csv({lista(lf)}, union_by_name=true, ignore_errors=true, {TLOG})")
        H = range(7, 24)
        def em(off, alias="l"):      # votos na hora cheia (prazo + off)
            return " + ".join(f"case when o.mah + 9 + {off} = {h} then {alias}.h{h:02d} else 0 end" for h in H)
        def desde(off, alias="l"):   # votos a partir da hora cheia (prazo + off)
            return " + ".join(f"case when o.mah + 9 + {off} <= {h} then {alias}.h{h:02d} else 0 end" for h in H)
        J = "from lt l join off o on o.uf = l.uf and o.cd_municipio = l.cd_municipio"
        n, tot_v, apos, h0, h1, h2 = c.execute(f"select count(*), sum(l.votos), sum({desde(0)}), sum({em(0)}), sum({em(1)}), sum({desde(2)}) {J}").fetchone()
        vt = {"secoes": int(n), "votos_dia": int(tot_v or 0), "apos_prazo": int(apos or 0), "h0": int(h0 or 0), "h1": int(h1 or 0), "h2": int(h2 or 0)}
        vt["por_uf"] = [dict(zip(["uf", "secoes", "apos"], r)) for r in c.execute(
            f"select l.uf, count(*), sum({desde(0)}) {J} group by 1 order by 3 desc").fetchall()]
        vt["top_mun"] = [dict(zip(["uf", "municipio", "secoes", "apos"], r)) for r in c.execute(
            f"select l.uf, l.municipio, count(*), sum({desde(0)}) {J} group by 1,2 order by 4 desc limit 10").fetchall()]
        qcols = [(hh, mm) for hh in range(15, 21) for mm in (0, 15, 30, 45)]
        if all(f"q{hh:02d}{mm:02d}" in [x[0] for x in c.execute("describe lt").fetchall()] for hh, mm in qcols):
            vt["q15"] = []
            for off in range(0, 150, 15):
                expr = " + ".join(f"case when (o.mah + 9) * 60 + {off} = {hh * 60 + mm} then l.q{hh:02d}{mm:02d} else 0 end" for hh, mm in qcols)
                vt["q15"].append({"b": off, "n": int(c.execute(f"select sum({expr}) {J}").fetchone()[0] or 0)})
        # estimativa para as seções que fecharam em até 30 min do prazo (a fila normal): média da amostra de 1% x nº de seções
        sf = sorted(PQ.glob("votes_by_hour_2t_*_amostra100.csv"))
        if sf:
            c.execute(f"create or replace table am as select * from read_csv({lista(sf)}, union_by_name=true, ignore_errors=true, {TLOG})")
            acols = " + ".join(f"case when o.mah + 9 <= {h} then a.h{h:02d} else 0 end" for h in H)
            r = c.execute(f"""select count(*), sum({acols}) from am a join off o on o.uf = a.uf and o.cd_municipio = a.cd_municipio
                join bu3 b on b.uf = a.uf and b.cd_municipio = a.cd_municipio and b.zona = a.zona and b.secao = a.secao where b.atraso < 30""").fetchone()
            resto = int(c.execute("select count(*) from bu3 where atraso < 30").fetchone()[0])
            if r[0]:
                vt["resto"] = {"amostra": int(r[0]), "media": round(r[1] / r[0], 2), "secoes": resto, "estimativa": int(round(r[1] / r[0] * resto))}
        data["votos_tardios"] = vt

# ---------- 2. nulos (RDV completo das UFs concluídas; sem nenhuma concluída, cai para a amostra 1 em 20) ----------
if ufs_ok:
    files = [PQ / f"rdvfull_2t_{u}.csv" for u in ufs_ok]
    fonte = "todas as seções de " + ", ".join(ufs_ok) + ("" if len(ufs_ok) == TOTAL_UFS else " (UFs concluídas até agora; a coleta continua)")
    c.execute(f"""create table rdv as select uf, cd_municipio, zona, secao, cargo, tipo, digitos, max(qtd) qtd
        from read_csv({lista(files)}, union_by_name=true, ignore_errors=true, {TIPOS}) group by 1,2,3,4,5,6,7""")
else:
    files, fonte = [PQ / f"rdv_2t_{u}.csv" for u in done("rdv_2t")], "amostra de 1 em cada 20 seções (nenhuma UF concluída ainda)"
    if files:
        c.execute(f"""create table rdv as select uf, cd_municipio, zona, secao, cargo, tipo, digitos, qtd
            from read_csv({lista(files)}, union_by_name=true, ignore_errors=true, {TIPOS})""")
data["nulos_fonte"] = fonte
if files:
    data["totais"] = [dict(zip(["cargo", "total", "nominais", "brancos", "nulos"], [int(x or 0) for x in r])) for r in c.execute("""
        select cargo, sum(qtd), sum(case when tipo=2 then qtd end), sum(case when tipo=3 then qtd end), sum(case when tipo=4 then qtd end)
        from rdv where cargo=1 group by 1""").fetchall()]
    elim = {70: "Cury (Avante)", 14: "Renan Santos (Missão)", 55: "Caiado (PSD)", 30: "Zema (Novo)", 80: "Samara (UP)"}
    tot = c.execute("select coalesce(sum(qtd),0) from rdv where cargo=1 and tipo=4").fetchone()[0]
    rows = c.execute("select digitos, sum(qtd) q from rdv where cargo=1 and tipo=4 group by 1 order by q desc limit 15").fetchall()
    case = f"""case when digitos in ({','.join(repr(str(k)) for k in elim)}) then 'Candidato eliminado no 1º turno'
         when digitos='00' then 'Zeros (00)'
         when digitos in (select distinct digitos from rdv r2 where r2.cargo=3 and r2.tipo=2 and r2.uf = rdv.uf) then 'Número de candidato a governador'
         else 'Outro número inexistente' end"""
    cl = c.execute(f"select {case} k, sum(qtd) from rdv where cargo=1 and tipo=4 group by 1 order by 2 desc").fetchall()
    data["nulos_digitos"] = {"pres": [{"digitos": d or "(vazio)", "qtd": int(q)} for d, q in rows]}
    data["nulos_digitos_todos"] = [{"d": d or "(vazio)", "q": int(q)} for d, q in c.execute("select digitos, sum(qtd) q from rdv where cargo=1 and tipo=4 group by 1 order by q desc").fetchall()]
    data["nulos_classes"] = {"pres": [{"classe": k, "qtd": int(q), "pct": round(100 * q / tot, 2) if tot else 0} for k, q in cl]}
    data["elim"] = {str(k): v for k, v in elim.items()}
    data["nulos_uf"] = [dict(zip(["uf", "total", "nulos", "brancos", "top", "top_q"], r)) for r in c.execute("""
        with t as (select uf, sum(qtd) total, sum(case when tipo=4 then qtd end) nulos, sum(case when tipo=3 then qtd end) brancos
                   from rdv where cargo=1 group by uf),
        d as (select uf, digitos, sum(qtd) q, row_number() over (partition by uf order by sum(qtd) desc) rn
              from rdv where cargo=1 and tipo=4 group by uf, digitos)
        select t.uf, t.total, t.nulos, t.brancos, d.digitos, d.q from t join d on d.uf=t.uf and d.rn=1
        order by t.nulos*1.0/t.total desc""").fetchall()]
    nomes = dict(c.execute("select distinct lpad(cd_municipio,5,'0'), municipio from bu").fetchall()) if bu_files else {}
    tot_n, tot_v = c.execute("select sum(case when tipo=4 then qtd end), sum(qtd) from rdv where cargo=1").fetchone()
    media = 100.0 * tot_n / tot_v
    ms = [{"uf": u, "municipio": nomes.get(str(cd).zfill(5), str(cd)), "total": int(tv), "nulos": int(nv or 0), "pct": round(100.0 * (nv or 0) / tv, 3)}
          for u, cd, tv, nv in c.execute("select uf, cd_municipio, sum(qtd), sum(case when tipo=4 then qtd end) from rdv where cargo=1 group by uf, cd_municipio having sum(qtd) >= 50000").fetchall()]
    ms.sort(key=lambda r: r["pct"])
    data["nulos_media"] = round(media, 3)
    data["nulos_mun_div"] = ms[-8:][::-1] + ms[:8][::-1] if len(ms) > 16 else ms[::-1]

# ---------- 3. juventude ----------
zt1 = PQ / "zona_t1.parquet"
if zt1.exists():
    data["juventude_t1"] = idade_vias.juventude_decis(c)

    # 2º turno × 1º turno por zona, só nas UFs concluídas (sem ZZ)
    inc = ",".join(repr(u) for u in ufs_ok if u != "ZZ")
    if bu_files and inc:
        c.execute(f"""create table z2 as select uf, lpad(cd_municipio,5,'0') mun, cast(zona as int) zona,
            sum(comparecimento) comp2,
            sum(coalesce(try_cast(regexp_extract(pres_nominais,'(?:^|;)13:(\\d+)',1) as int),0)) lula2,
            sum(coalesce(try_cast(regexp_extract(pres_nominais,'(?:^|;)22:(\\d+)',1) as int),0)) flavio2
            from bu where uf in ({inc}) group by 1,2,3""")
        rows = c.execute(f"""
          with j as (select t.uf, t.mun, t.zona, t.lula, t.flavio, t.aptos, t.comp, t.comp_16_24, z2.comp2, z2.lula2, z2.flavio2
                     from (select *, lpad(mun,5,'0') mun5 from '{zt1}') t
                     join z2 on z2.uf=t.uf and z2.mun=t.mun5 and z2.zona=t.zona
                     where t.comp>0 and z2.lula2+z2.flavio2>0),
          q as (select *, comp_16_24*1.0/comp jov, ntile(10) over (order by comp_16_24*1.0/comp) decil from j)
          select decil, count(*) zonas, round(100*avg(jov),1) jov_medio,
                 round(100*sum(lula)/sum(lula+flavio),2) lula_t1, round(100*sum(lula2)/sum(lula2+flavio2),2) lula_t2,
                 round(100*sum(comp)/sum(aptos),1) comp_t1, round(100*sum(comp2)/sum(aptos),1) comp_t2
          from q group by 1 order by 1""").fetchall()
        data["juventude_t2"] = {"ufs": [u for u in ufs_ok if u != "ZZ"],
            "decis": [dict(zip(["decil", "zonas", "jov_medio", "lula_t1", "lula_t2", "comp_t1", "comp_t2"], r)) for r in rows]}

# ---------- idade e terceiras vias, por tipo de zona ----------
sys.path.insert(0, str(ROOT / "scripts"))
import idade_vias
if zt1.exists() and (PQ / "perfil_comp_abst_2026.parquet").exists():
    data["vias_t1"] = idade_vias.t1(c)
    data["vias_perfil"] = idade_vias.perfil_cand(c)
    if "juventude_t2" in data:
        data["vias_t2"] = {"ufs": data["juventude_t2"]["ufs"], **idade_vias.t2(c)}

# ---------- comparecimento por idade (1º turno) ----------
pca = PQ / "perfil_comp_abst_2026.parquet"
if pca.exists():
    rows = c.execute(f"""select DS_FAIXA_ETARIA, sum(QT_APTOS), sum(QT_COMPARECIMENTO),
        100.0*sum(QT_COMPARECIMENTO)/sum(QT_APTOS) from '{pca}' where NR_TURNO=1 and CD_FAIXA_ETARIA>0
        group by CD_FAIXA_ETARIA, DS_FAIXA_ETARIA order by CD_FAIXA_ETARIA""").fetchall()
    data["comparecimento_idade"] = [{"faixa": r[0].replace(" anos", "").replace("100 ou mais", "100+"), "aptos": int(r[1]), "comp": int(r[2]), "pct": round(r[3], 1)} for r in rows]

# ---------- mapa por UF ----------
mapa = {}
if zt1.exists() and (PQ / "perfil_comp_abst_2026.parquet").exists():
    mapa.update(idade_vias.mapa_t1(c))
for chave, sql in (("lula_t2", "select uf, 100.0*sum(lula2)/sum(lula2+flavio2) from z2 group by uf"),
                   ("nulos", "select uf, 100.0*sum(case when tipo=4 then qtd end)/sum(qtd) from rdv where cargo=1 group by uf")):
    try:
        mapa[chave] = {u: round(v, 2) for u, v in c.execute(sql).fetchall()}
    except Exception:
        pass
if "pror" in data:
    mapa["prorrogadas"] = {r["uf"]: round(100.0 * r["n105"] / r["secoes"], 2) for r in data["pror"]["por_uf"]}
data["mapa"] = mapa

# mapa por município (códigos IBGE): 1º turno completo; 2º turno das UFs concluídas
mm = {}
t2i = ROOT / "out" / "tse2ibge.json"
if t2i.exists() and zt1.exists() and (PQ / "perfil_comp_abst_2026.parquet").exists():
    tse2ibge = json.loads(t2i.read_text())
    def ib(d):
        return {tse2ibge[k.zfill(5)]: v for k, v in d.items() if k.zfill(5) in tse2ibge}
    mm = {k: ib(v) for k, v in idade_vias.mapa_mun_t1(c).items()}
    for chave, sql in (("lula_t2", "select mun, 100.0*sum(lula2)/sum(lula2+flavio2) from z2 group by mun having sum(lula2+flavio2) > 0"),
                       ("nulos", "select lpad(cd_municipio,5,'0'), 100.0*sum(case when tipo=4 then qtd end)/sum(qtd) from rdv where cargo=1 group by 1"),
                       ("prorrogadas", "select lpad(cd_municipio,5,'0'), 100.0*sum(case when atraso>=105 then 1 else 0 end)/count(*) from bu3 group by 1")):
        try:
            mm[chave] = ib({k: round(v, 2) for k, v in c.execute(sql).fetchall() if v is not None})
        except Exception:
            pass
(OUT / "dados_mun.js").write_text("const DADOS_MUN=" + json.dumps(mm, separators=(",", ":")) + ";\n")

(OUT / "dados.json").write_text(json.dumps(data, ensure_ascii=False, indent=1))
tpl = (OUT / "template.html").read_text()
(OUT / "index.html").write_text(tpl.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False)))
print(f"ok: {secoes_ok:,} seções coletadas | UFs concluídas: {len(ufs_ok)} | nulos: {fonte}")
