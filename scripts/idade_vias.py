"""Idade do eleitorado e terceiras vias, por tipo de zona (quem ficou em 1º lugar).

A idade só existe por zona eleitoral (o TSE não publica idade por seção), então o "local" é a zona.
- 1º turno: país inteiro (cacheado em out/idade_vias_t1.json, pois não muda).
- 2º turno: zonas das UFs concluídas, agrupadas por quem venceu o 2º turno (usa a tabela z2 criada pelo gerador).
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "out" / "idade_vias_t1.json"
REG = {"Norte": "AC AP AM PA RO RR TO", "Nordeste": "AL BA CE MA PB PE PI RN SE", "Centro-Oeste": "DF GO MT MS",
       "Sudeste": "ES MG RJ SP", "Sul": "PR RS SC"}
REGIAO = {u: r for r, us in REG.items() for u in us.split()}
VIAS = ["cury", "renan", "caiado", "zema"]
NOMES = {"cury": "Cury (Avante)", "renan": "Renan Santos (Missão)", "caiado": "Caiado (PSD)", "zema": "Zema (Novo)", "outros": "Demais candidatos"}
FAIXAS = (
    "case CD_FAIXA_ETARIA when 1600 then 16 when 1700 then 17 when 1800 then 18 when 1900 then 19 when 2000 then 20 when 2124 then 22.5 "
    "when 2529 then 27 when 3034 then 32 when 3539 then 37 when 4044 then 42 when 4549 then 47 when 5054 then 52 when 5559 then 57 "
    "when 6064 then 62 when 6569 then 67 when 7074 then 72 when 7579 then 77 when 8084 then 82 when 8589 then 87 when 9094 then 92 "
    "when 9599 then 97 when 9999 then 102 else null end")

def _stats(c, src, grp, extra=""):
    cols = ["g", "zonas", "eleitores", "idade", "j", "a", "b", "s", "lula", "flavio", "cury", "renan", "caiado", "zema", "outros"]
    q = f"""select {grp} g, count(*) zonas, sum(comp) eleitores, sum(idade_media*comp)/sum(comp) idade,
        100.0*sum(j1624)/sum(comp), 100.0*sum(a2539)/sum(comp), 100.0*sum(a4059)/sum(comp), 100.0*sum(a60)/sum(comp),
        100.0*sum(lula)/sum(validos), 100.0*sum(flavio)/sum(validos), 100.0*sum(cury)/sum(validos), 100.0*sum(renan)/sum(validos),
        100.0*sum(caiado)/sum(validos), 100.0*sum(zema)/sum(validos), 100.0*sum(outros)/sum(validos) {extra}
        from {src} group by 1 order by 1"""
    out = []
    for r in c.execute(q).fetchall():
        d = dict(zip(cols, r))
        for k in cols[3:]:
            d[k] = round(d[k], 2)
        d["zonas"], d["eleitores"] = int(d["zonas"]), int(d["eleitores"])
        d["terceira"] = round(sum(d[k] for k in VIAS + ["outros"]), 2)
        out.append(d)
    return out

def _melhor(c, src, grp):
    return [dict(g=g, via=v, zonas=int(n)) for g, v, n in c.execute(f"""
        select {grp}, case greatest(cury,renan,caiado,zema) when cury then 'cury' when renan then 'renan' when caiado then 'caiado' else 'zema' end b, count(*)
        from {src} group by 1,2 order by 1,3 desc""").fetchall()]

def _tabela_g(c):
    """Tabela g: uma linha por zona, com votos do 1º turno e perfil de idade de quem compareceu."""
    c.execute("""create or replace view cand as select SG_UF uf, lpad(CD_MUNICIPIO,5,'0') mun, NR_ZONA zona, NR_CANDIDATO nr, QT_VOTOS_NOMINAIS v
        from read_csv('data/raw/tse/cand/votacao_candidato_munzona_2026_BR.csv', delim=';', quote='"', encoding='latin-1', header=true, types={'CD_MUNICIPIO':'VARCHAR'})""")
    c.execute(f"""create or replace table idade_z as select SG_UF uf, lpad(CD_MUNICIPIO,5,'0') mun, NR_ZONA zona, sum(QT_COMPARECIMENTO) comp,
        sum(QT_COMPARECIMENTO * {FAIXAS})/nullif(sum(case when CD_FAIXA_ETARIA>0 then QT_COMPARECIMENTO end),0) idade_media,
        sum(case when CD_FAIXA_ETARIA between 1600 and 2124 then QT_COMPARECIMENTO else 0 end) j1624,
        sum(case when CD_FAIXA_ETARIA between 2529 and 3539 then QT_COMPARECIMENTO else 0 end) a2539,
        sum(case when CD_FAIXA_ETARIA between 4044 and 5559 then QT_COMPARECIMENTO else 0 end) a4059,
        sum(case when CD_FAIXA_ETARIA >= 6064 then QT_COMPARECIMENTO else 0 end) a60
        from 'data/parquet/perfil_comp_abst_2026.parquet' where NR_TURNO=1 group by 1,2,3""")
    c.execute("""create or replace table z1 as select uf, mun, zona, sum(v) validos,
        sum(case when nr=13 then v else 0 end) lula, sum(case when nr=22 then v else 0 end) flavio,
        sum(case when nr=70 then v else 0 end) cury, sum(case when nr=14 then v else 0 end) renan,
        sum(case when nr=55 then v else 0 end) caiado, sum(case when nr=30 then v else 0 end) zema,
        sum(case when nr not in (13,22,70,14,55,30) then v else 0 end) outros from cand group by 1,2,3""")
    reg = ",".join(f"('{u}','{r}')" for u, r in REGIAO.items())
    c.execute(f"create or replace table regiao_uf as select * from (values {reg}) t(uf, regiao)")
    c.execute("""create or replace table g as select z1.*, i.comp, i.idade_media, i.j1624, i.a2539, i.a4059, i.a60, r.regiao
        from z1 join idade_z i using (uf, mun, zona) left join regiao_uf r using (uf) where z1.validos > 0 and i.comp > 0""")

def _grupo_expr(m):
    return f"""case when {m} > 5 then '1 Lula venceu (mais de 5 pontos)' when {m} < -5 then '3 Flávio venceu (mais de 5 pontos)'
                    else '2 Disputada (até 5 pontos)' end"""

def t1(c):
    if CACHE.exists():
        return json.loads(CACHE.read_text())
    _tabela_g(c)
    c.execute(f"create or replace table g1 as select *, {_grupo_expr('(lula-flavio)*100.0/validos')} grupo from g")
    forte = []
    for nm in VIAS:
        r = c.execute(f"""with q as (select *, {nm}*1.0/validos p, ntile(10) over (order by {nm}*1.0/validos) d from g)
            select 100*avg(p) filter (where d=10), sum(idade_media*comp) filter (where d=10)/sum(comp) filter (where d=10),
                   100.0*sum(j1624) filter (where d=10)/sum(comp) filter (where d=10),
                   sum(idade_media*comp) filter (where d=1)/sum(comp) filter (where d=1),
                   100.0*sum(j1624) filter (where d=1)/sum(comp) filter (where d=1) from q""").fetchone()
        forte.append({"via": nm, "pct_forte": round(r[0], 2), "idade_forte": round(r[1], 1), "jov_forte": round(r[2], 1),
                      "idade_fraca": round(r[3], 1), "jov_fraca": round(r[4], 1)})
    res = {"grupos": _stats(c, "g1", "grupo"), "melhor": _melhor(c, "g1", "grupo"), "forte": forte,
           "regioes": _stats(c, "g", "coalesce(regiao,'Exterior')"), "melhor_regiao": _melhor(c, "g", "coalesce(regiao,'Exterior')"),
           "zonas": int(c.execute("select count(*) from g").fetchone()[0]), "eleitores": int(c.execute("select sum(comp) from g").fetchone()[0])}
    # idade das zonas onde cada candidato foi votado: cada zona entra com peso = votos do candidato nela
    cands = []
    ref = c.execute("""select sum(comp), sum(idade_media*comp)/sum(comp), 100.0*sum(j1624)/sum(comp), 100.0*sum(a2539)/sum(comp),
                       100.0*sum(a4059)/sum(comp), 100.0*sum(a60)/sum(comp) from g""").fetchone()
    cands.append(dict(k="todos", votos=int(ref[0]), idade=round(ref[1], 2), j=round(ref[2], 2), a=round(ref[3], 2), b=round(ref[4], 2), s=round(ref[5], 2)))
    for k in ["lula", "flavio"] + VIAS + ["outros"]:
        r = c.execute(f"""select sum({k}), sum({k}*idade_media)/sum({k}), 100.0*sum({k}*j1624*1.0/comp)/sum({k}), 100.0*sum({k}*a2539*1.0/comp)/sum({k}),
                          100.0*sum({k}*a4059*1.0/comp)/sum({k}), 100.0*sum({k}*a60*1.0/comp)/sum({k}) from g""").fetchone()
        cands.append(dict(k=k, votos=int(r[0]), idade=round(r[1], 2), j=round(r[2], 2), a=round(r[3], 2), b=round(r[4], 2), s=round(r[5], 2)))
    res["candidatos"] = cands
    res["corr"] = [dict(regiao=r[0], zonas=int(r[1]), lula=round(r[2], 2), flavio=round(r[3], 2), renan=round(r[4], 2), terceira=round(r[5], 2))
                   for r in c.execute("""select coalesce(regiao,'Exterior'), count(*), corr(j1624*1.0/comp, lula*1.0/validos),
                       corr(j1624*1.0/comp, flavio*1.0/validos), corr(j1624*1.0/comp, renan*1.0/validos),
                       corr(j1624*1.0/comp, (cury+renan+caiado+zema+outros)*1.0/validos) from g group by 1 order by 1""").fetchall()]
    CACHE.write_text(json.dumps(res, ensure_ascii=False))
    return res

def t2(c):
    """2º turno: zonas das UFs concluídas (tabela z2 já criada), por quem venceu o 2º turno."""
    try:
        c.execute("select 1 from g limit 1")
    except Exception:
        _tabela_g(c)
    c.execute("create or replace table g2base as select g.*, z2.lula2, z2.flavio2, z2.comp2 from g join z2 on z2.uf=g.uf and z2.mun=g.mun and z2.zona=g.zona where z2.lula2+z2.flavio2 > 0")
    m = "(lula2-flavio2)*100.0/(lula2+flavio2)"
    c.execute(f"create or replace table g2 as select *, {_grupo_expr(m)} grupo from g2base")
    ex = ", 100.0*sum(lula2)/sum(lula2+flavio2) lula_t2"
    cols = _stats(c, "g2", "grupo")
    t2s = {r[0]: round(r[1], 2) for r in c.execute("select grupo, 100.0*sum(lula2)/sum(lula2+flavio2) from g2 group by 1").fetchall()}
    for d in cols:
        d["lula_t2"] = t2s.get(d["g"])
    return {"grupos": cols, "melhor": _melhor(c, "g2", "grupo")}

DIMS = {
    "Gênero": ("case CD_GENERO when 4 then 'Mulheres' when 2 then 'Homens' end", ["Mulheres"]),
    "Escolaridade": ("case CD_GRAU_INSTRUCAO when 1 then 'Analfabeto ou lê e escreve' when 2 then 'Analfabeto ou lê e escreve' "
                     "when 3 then 'Fundamental incompleto' when 4 then 'Fundamental completo' when 5 then 'Médio incompleto' "
                     "when 6 then 'Médio completo' when 7 then 'Superior incompleto' when 8 then 'Superior completo' end",
                     ["Analfabeto ou lê e escreve", "Fundamental incompleto", "Fundamental completo", "Médio incompleto", "Médio completo", "Superior incompleto", "Superior completo"]),
    "Idade": ("case when CD_FAIXA_ETARIA between 1600 and 2124 then '16 a 24 anos' when CD_FAIXA_ETARIA between 2529 and 3539 then '25 a 39 anos' "
              "when CD_FAIXA_ETARIA between 4044 and 5559 then '40 a 59 anos' when CD_FAIXA_ETARIA >= 6064 then '60 anos ou mais' end",
              ["16 a 24 anos", "25 a 39 anos", "40 a 59 anos", "60 anos ou mais"]),
    "Estado civil": ("case CD_ESTADO_CIVIL when 1 then 'Solteiro(a)' when 3 then 'Casado(a)' when 5 then 'Viúvo(a)' when 7 then 'Separado(a) ou divorciado(a)' when 9 then 'Separado(a) ou divorciado(a)' end",
                     ["Solteiro(a)", "Casado(a)", "Separado(a) ou divorciado(a)", "Viúvo(a)"]),
    "Cor/raça (só 21% declararam)": ("case CD_COR_RACA when 1 then 'Branca' when 3 then 'Parda' when 2 then 'Preta' when 4 then 'Indígena ou amarela' when 5 then 'Indígena ou amarela' end",
                                      ["Branca", "Parda", "Preta", "Indígena ou amarela"]),
}
PCACHE = ROOT / "out" / "perfil_cand_t1.json"

def perfil_cand(c):
    """Perfil do eleitorado (quem compareceu no 1º turno) nas zonas onde cada candidato foi votado.
    Cada zona pesa pelos votos que o candidato teve nela. Retorna a parcela de cada categoria por candidato."""
    if PCACHE.exists():
        return json.loads(PCACHE.read_text())
    try:
        c.execute("select 1 from z1 limit 1")
    except Exception:
        _tabela_g(c)
    ks = ["lula", "flavio"] + VIAS + ["v3"]   # v3 = terceiras vias somadas (todo mundo que não é Lula nem Flávio)
    w = {k: k for k in ks}; w["v3"] = "(cury+renan+caiado+zema+outros)"
    sel = ", ".join(f"100.0*sum(sh*{w[k]})/sum({w[k]})" for k in ks)
    out = []
    for dim, (expr, ordem) in DIMS.items():
        rows = c.execute(f"""
          with p as (select SG_UF uf, lpad(CD_MUNICIPIO,5,'0') mun, NR_ZONA zona, {expr} cat, sum(QT_COMPARECIMENTO) q
                     from 'data/parquet/perfil_comp_abst_2026.parquet' where NR_TURNO=1 and ({expr}) is not null group by 1,2,3,4),
          t as (select uf, mun, zona, sum(q) tot from p group by 1,2,3),
          j as (select p.cat, p.q*1.0/t.tot sh, t.tot, z1.lula, z1.flavio, z1.cury, z1.renan, z1.caiado, z1.zema, z1.outros
                from p join t using (uf, mun, zona) join z1 using (uf, mun, zona) where t.tot > 0)
          select cat, 100.0*sum(sh*tot)/sum(tot), {sel} from j group by cat""").fetchall()
        por = {r[0]: r for r in rows}
        # "Mulheres": a categoria única; as demais seguem a ordem
        out.append({"dim": dim, "linhas": [dict(cat=cat, ref=round(por[cat][1], 2), **{k: round(por[cat][2 + i], 2) for i, k in enumerate(ks)})
                                           for cat in ordem if cat in por]})
    res = {"cands": ks, "dims": out}
    PCACHE.write_text(json.dumps(res, ensure_ascii=False))
    return res


MCACHE = ROOT / "out" / "mapa_t1.json"

def _garante_g(c):
    try:
        c.execute("select 1 from g limit 1")
    except Exception:
        _tabela_g(c)

def juventude_decis(c):
    """1º turno: 10 grupos de zonas (mesmo tamanho) pela parcela de jovens de 16–24 anos entre quem compareceu."""
    _garante_g(c)
    cols = ["decil", "zonas", "jov_medio", "lula", "flavio", "cury", "renan", "caiado", "zema"]
    rows = c.execute("""with q as (select *, j1624*1.0/comp jov, ntile(10) over (order by j1624*1.0/comp) decil from g)
        select decil, count(*), 100*avg(jov), 100.0*sum(lula)/sum(validos), 100.0*sum(flavio)/sum(validos), 100.0*sum(cury)/sum(validos),
               100.0*sum(renan)/sum(validos), 100.0*sum(caiado)/sum(validos), 100.0*sum(zema)/sum(validos)
        from q group by 1 order by 1""").fetchall()
    return [dict(zip(cols, [int(r[0]), int(r[1])] + [round(x, 2) for x in r[2:]])) for r in rows]

def mapa_t1(c):
    """Métricas do 1º turno por UF (país inteiro), para o mapa."""
    if MCACHE.exists():
        return json.loads(MCACHE.read_text())
    _garante_g(c)
    names = ["terceiras", "renan", "cury", "caiado", "zema", "lula_t1"]
    out = {k: {} for k in names + ["idade"]}
    for r in c.execute("""select uf, 100.0*sum(cury+renan+caiado+zema+outros)/sum(validos), 100.0*sum(renan)/sum(validos),
            100.0*sum(cury)/sum(validos), 100.0*sum(caiado)/sum(validos), 100.0*sum(zema)/sum(validos), 100.0*sum(lula)/sum(lula+flavio)
            from z1 group by uf""").fetchall():
        for k, v in zip(names, r[1:]):
            out[k][r[0]] = round(v, 2)
    for u, v in c.execute("select uf, sum(idade_media*comp)/sum(comp) from idade_z group by uf").fetchall():
        out["idade"][u] = round(v, 2)
    MCACHE.write_text(json.dumps(out, ensure_ascii=False))
    return out


MMCACHE = ROOT / "out" / "mapa_mun_t1.json"

def mapa_mun_t1(c):
    """Métricas do 1º turno por município (código TSE de 5 dígitos), país inteiro."""
    if MMCACHE.exists():
        return json.loads(MMCACHE.read_text())
    _garante_g(c)
    names = ["terceiras", "renan", "cury", "caiado", "zema", "lula_t1"]
    out = {k: {} for k in names + ["idade"]}
    for r in c.execute("""select mun, 100.0*sum(cury+renan+caiado+zema+outros)/sum(validos), 100.0*sum(renan)/sum(validos),
            100.0*sum(cury)/sum(validos), 100.0*sum(caiado)/sum(validos), 100.0*sum(zema)/sum(validos),
            100.0*sum(lula)/nullif(sum(lula+flavio),0) from z1 where uf <> 'ZZ' group by mun having sum(validos) > 0""").fetchall():
        for k, v in zip(names, r[1:]):
            if v is not None:
                out[k][r[0]] = round(v, 2)
    for u, v in c.execute("select mun, sum(idade_media*comp)/sum(comp) from idade_z where uf <> 'ZZ' group by mun having sum(comp) > 0").fetchall():
        out["idade"][u] = round(v, 2)
    MMCACHE.write_text(json.dumps(out, ensure_ascii=False))
    return out
