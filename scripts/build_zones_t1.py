"""Base por zona eleitoral do 1º turno: voto presidencial + perfil de quem compareceu."""
import duckdb
c = duckdb.connect()
c.execute("""create view cand as select * from read_csv('data/raw/tse/cand/votacao_candidato_munzona_2026_BR.csv',
  delim=';', quote='"', encoding='latin-1', header=true, types={'CD_MUNICIPIO':'VARCHAR'})""")
# votos por candidato e zona (colunas por candidato principal)
c.execute("""create table votos as select SG_UF uf, CD_MUNICIPIO mun, NR_ZONA zona,
  any_value(NM_MUNICIPIO) municipio,
  sum(QT_VOTOS_NOMINAIS) validos,
  sum(case when NR_CANDIDATO=13 then QT_VOTOS_NOMINAIS end) lula,
  sum(case when NR_CANDIDATO=22 then QT_VOTOS_NOMINAIS end) flavio,
  sum(case when NR_CANDIDATO=14 then QT_VOTOS_NOMINAIS end) renan,
  sum(case when NR_CANDIDATO=70 then QT_VOTOS_NOMINAIS end) cury,
  sum(case when NR_CANDIDATO=55 then QT_VOTOS_NOMINAIS end) caiado
  from cand group by 1,2,3""")
# perfil de comparecimento do 1º turno por faixa etária
c.execute("""create table idade as select SG_UF uf, CD_MUNICIPIO mun, NR_ZONA zona,
  sum(QT_APTOS) aptos, sum(QT_COMPARECIMENTO) comp,
  sum(case when CD_FAIXA_ETARIA<=2124 then QT_COMPARECIMENTO else 0 end) comp_16_24,
  sum(case when CD_FAIXA_ETARIA>=2529 and CD_FAIXA_ETARIA<=3539 then QT_COMPARECIMENTO else 0 end) comp_25_39,
  sum(case when CD_FAIXA_ETARIA>=4044 and CD_FAIXA_ETARIA<=5559 then QT_COMPARECIMENTO else 0 end) comp_40_59,
  sum(case when CD_FAIXA_ETARIA>=6064 then QT_COMPARECIMENTO else 0 end) comp_60mais,
  sum(case when CD_FAIXA_ETARIA<=2124 then QT_APTOS else 0 end) aptos_16_24
  from 'data/parquet/perfil_comp_abst_2026.parquet' where NR_TURNO=1 group by 1,2,3""")
c.execute("""copy (select v.*, i.aptos, i.comp, i.comp_16_24, i.comp_25_39, i.comp_40_59, i.comp_60mais, i.aptos_16_24
  from votos v join idade i using (uf, mun, zona)) to 'data/parquet/zona_t1.parquet' (format parquet)""")
print(c.execute("select count(*), sum(validos), sum(comp), sum(comp_16_24)*1.0/sum(comp) from 'data/parquet/zona_t1.parquet'").fetchall())
print(c.execute("select distinct CD_FAIXA_ETARIA, DS_FAIXA_ETARIA from 'data/parquet/perfil_comp_abst_2026.parquet' order by 1").fetchall())
