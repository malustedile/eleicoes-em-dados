"""Idade do eleitorado e terceiras vias, por tipo de zona (quem ficou em 1º lugar).
1º turno: país inteiro (votação por zona + perfil de quem compareceu). Imprime tabelas; o dashboard usa a versão em JSON.
"""
import duckdb
c = duckdb.connect()
c.execute("""create view cand as select SG_UF uf, lpad(CD_MUNICIPIO,5,'0') mun, NR_ZONA zona, NR_CANDIDATO nr, NM_URNA_CANDIDATO nome, QT_VOTOS_NOMINAIS v
  from read_csv('data/raw/tse/cand/votacao_candidato_munzona_2026_BR.csv', delim=';', quote='"', encoding='latin-1', header=true, types={'CD_MUNICIPIO':'VARCHAR'})""")
# idade média estimada (ponto médio da faixa) e faixas, só de quem compareceu
c.execute("""create table idade as select SG_UF uf, lpad(CD_MUNICIPIO,5,'0') mun, NR_ZONA zona,
  sum(QT_COMPARECIMENTO) comp,
  sum(QT_COMPARECIMENTO * case CD_FAIXA_ETARIA when 1600 then 16 when 1700 then 17 when 1800 then 18 when 1900 then 19 when 2000 then 20
     when 2124 then 22.5 when 2529 then 27 when 3034 then 32 when 3539 then 37 when 4044 then 42 when 4549 then 47 when 5054 then 52
     when 5559 then 57 when 6064 then 62 when 6569 then 67 when 7074 then 72 when 7579 then 77 when 8084 then 82 when 8589 then 87
     when 9094 then 92 when 9599 then 97 when 9999 then 102 else null end)/nullif(sum(case when CD_FAIXA_ETARIA>0 then QT_COMPARECIMENTO end),0) idade_media,
  sum(case when CD_FAIXA_ETARIA between 1600 and 2124 then QT_COMPARECIMENTO else 0 end) j1624,
  sum(case when CD_FAIXA_ETARIA between 2529 and 3539 then QT_COMPARECIMENTO else 0 end) a2539,
  sum(case when CD_FAIXA_ETARIA between 4044 and 5559 then QT_COMPARECIMENTO else 0 end) a4059,
  sum(case when CD_FAIXA_ETARIA >= 6064 then QT_COMPARECIMENTO else 0 end) a60
  from 'data/parquet/perfil_comp_abst_2026.parquet' where NR_TURNO=1 group by 1,2,3""")
c.execute("""create table z as select uf, mun, zona,
  sum(v) validos,
  sum(case when nr=13 then v else 0 end) lula, sum(case when nr=22 then v else 0 end) flavio,
  sum(case when nr=70 then v else 0 end) cury, sum(case when nr=14 then v else 0 end) renan,
  sum(case when nr=55 then v else 0 end) caiado, sum(case when nr=30 then v else 0 end) zema,
  sum(case when nr not in (13,22,70,14,55,30) then v else 0 end) outros
  from cand group by 1,2,3""")
c.execute("""create table g as select z.*, i.comp, i.idade_media, i.j1624, i.a2539, i.a4059, i.a60,
  (lula-flavio)*100.0/validos margem,
  case when (lula-flavio)*100.0/validos > 5 then '1 Lula vence (mais de 5 pontos)'
       when (lula-flavio)*100.0/validos < -5 then '3 Flávio vence (mais de 5 pontos)' else '2 Disputada (até 5 pontos)' end grupo
  from z join idade i using (uf, mun, zona) where validos > 0 and i.comp > 0""")
print(c.execute("select count(*), sum(comp) from g").fetchone())
print("\n== IDADE por tipo de zona ==")
for r in c.execute("""select grupo, count(*) zonas, sum(comp) eleitores,
  round(sum(idade_media*comp)/sum(comp),1) idade_media,
  round(100.0*sum(j1624)/sum(comp),1) j, round(100.0*sum(a2539)/sum(comp),1) a, round(100.0*sum(a4059)/sum(comp),1) b, round(100.0*sum(a60)/sum(comp),1) s
  from g group by 1 order by 1""").fetchall(): print(r)
print("\n== TERCEIRAS VIAS (% dos votos válidos) por tipo de zona ==")
for r in c.execute("""select grupo, round(100.0*sum(lula)/sum(validos),1) lula, round(100.0*sum(flavio)/sum(validos),1) flavio,
  round(100.0*sum(cury)/sum(validos),2) cury, round(100.0*sum(renan)/sum(validos),2) renan, round(100.0*sum(caiado)/sum(validos),2) caiado,
  round(100.0*sum(zema)/sum(validos),2) zema, round(100.0*sum(outros)/sum(validos),2) outros,
  round(100.0*sum(cury+renan+caiado+zema+outros)/sum(validos),1) terceira_via
  from g group by 1 order by 1""").fetchall(): print(r)
print("\n== Qual terceira via foi a mais votada em cada zona (nº de zonas) ==")
for r in c.execute("""select grupo, best, count(*) from (select grupo, case greatest(cury,renan,caiado,zema) when cury then 'Cury' when renan then 'Renan' when caiado then 'Caiado' else 'Zema' end best from g) group by 1,2 order by 1,3 desc""").fetchall(): print(r)
print("\n== Perfil etário onde cada terceira via foi mais forte (10% das zonas com maior parcela dele) ==")
for nm in ("renan","cury","caiado","zema"):
    r=c.execute(f"""with q as (select *, {nm}*1.0/validos p, ntile(10) over (order by {nm}*1.0/validos) d from g)
      select '{nm}', round(100*avg(p) filter (where d=10),2) forte, round(sum(idade_media*comp) filter (where d=10)/sum(comp) filter (where d=10),1) idade_forte, round(100.0*sum(j1624) filter (where d=10)/sum(comp) filter (where d=10),1) jov_forte,
      round(sum(idade_media*comp) filter (where d=1)/sum(comp) filter (where d=1),1) idade_fraca from q""").fetchone(); print(r)
