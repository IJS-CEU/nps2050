"""11.6 Pot brez izkaznice: tipične vrednosti primarne energije po tipu × obdobju gradnje × ovoju × oknih × ogrevanju.

Vir: računske energetske izkaznice stanovanjskih stavb, povezane s katastrom; stanje ovoja in oken iz katastra (vpis obnove
2010 ali pozneje) in Eko sklada. Mediana in razpon P25–P75 primarne energije [kWh/(m²·a)], razred po mejah NPS 2050.
Če polna kombinacija nima vsaj MIN_N izkaznic, se oceni brez delitve po oknih, nato brez delitve po ovoju in oknih;
sicer ocene ni. Novejše stavbe (po 2002) so izolirane že ob gradnji. (Predlog poslan v potrditev 2. 10. 2026.)
"""
import json

import numpy as np
import pandas as pd

from .context import OUT, Context, write_json
from .stavbe import build_table

MIN_N = 20
PER = ['do 1945', '1946–1970', '1971–1980', '1981–1990', '1991–2002', '2003–2010', '2011–2020', 'po 2020']
NEW = {'2003–2010', '2011–2020', 'po 2020'}
OG = {'elko': 'olje', 'gas': 'plin', 'bio': 'les', 'tc': 'tc', 'dh': 'daljinsko', 'el': 'elektrika'}


def build(ctx: Context) -> dict:
    df = build_table(ctx)
    fond = json.loads((OUT / 'stavbni_fond.json').read_text(encoding='utf-8'))
    bnd = {c['id']: [c['class_bounds'][k] for k in ('A|B', 'B|C', 'C|D', 'D|E', 'E|F', 'F|G')] for c in fond['categories']}
    cls = lambda cat, v: 'ABCDEFG'[sum(v > b for b in bnd[cat])]
    e = df[df.cat.isin(['HISA', 'BLOKI']) & df.ei_pe.notna() & df.period.notna()].copy()
    sh = e[['ei_sh_gas', 'ei_sh_elko', 'ei_sh_bio', 'ei_sh_dh', 'ei_sh_el']].rename(columns=lambda c: c[6:])
    e['og'] = np.where(e.ei_sh_amb >= 0.15, 'tc', sh.idxmax(axis=1))
    e['og'] = e.og.map(OG)
    y = lambda c: pd.to_numeric(e[c], errors='coerce')
    new = e.period.astype(str).isin(NEW)
    fas = (y('obnova_fasada') >= 2010) | e.es_ovoj.notna()
    e['ovoj'] = np.select([new, fas, y('obnova_streha') >= 2010], ['izolirano', 'izolirano', 'delno'], 'neizolirano')
    e['okna'] = np.where(new | (y('obnova_okna') >= 2010) | e.es_okna.notna(), 'da', 'ne')
    e['per'] = e.period.astype(str)
    out, n_full, n_none = {}, 0, 0
    for cat in ('HISA', 'BLOKI'):
        a = e[e.cat == cat]
        for per in PER:
            ovs, oks = (['izolirano'], ['da']) if per in NEW else (['neizolirano', 'delno', 'izolirano'], ['ne', 'da'])
            for ov in ovs:
                for ok in oks:
                    for og in OG.values():
                        levels = [('polna', (a.per == per) & (a.ovoj == ov) & (a.okna == ok) & (a.og == og)),
                                  ('brez oken', (a.per == per) & (a.ovoj == ov) & (a.og == og)),
                                  ('brez ovoja in oken', (a.per == per) & (a.og == og))]
                        hit = next(((lab, m) for lab, m in levels if m.sum() >= MIN_N), None)
                        key = f'{cat}|{per}|{ov}|{ok}|{og}'
                        if hit is None:
                            n_none += 1
                            continue
                        lab, m = hit
                        n_full += lab == 'polna'
                        v = a.loc[m, 'ei_pe']
                        p25, med, p75 = (float(v.quantile(q)) for q in (.25, .5, .75))
                        out[key] = {'pe': round(med), 'p25': round(p25), 'p75': round(p75), 'od': cls(cat, p25), 'do': cls(cat, p75),
                                    'n': int(m.sum()), 'osnova': lab}
    ctx.check(n_full >= 150, f'arhetipi: {n_full} polnih kombinacij, {len(out)} z oceno, {n_none} brez ocene')
    data = {
        'meta': ctx.meta(['Register energetskih izkaznic (računske izkaznice stanovanjskih stavb) in kataster nepremičnin; Eko sklad (ovoj, okna)'],
                         note='Ocena na podlagi tipičnih stavb. Dejanski razred določi energetska izkaznica.'),
        'obdobja': PER, 'nova_obdobja': sorted(NEW), 'min_n': MIN_N, 'kombinacije': out,
    }
    write_json('arhetipi', data)
    return data
