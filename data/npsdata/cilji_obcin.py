"""Kaj državni cilji NPS 2050 pomenijo za občino (ponazoritev, ne obveznost občine).

- Obseg prenove: državni letni obseg po segmentih (preglednica »Potrebni obseg prenov …«, obdobji 2020–2030 in 2031–2040),
  razdeljen na občine po deležu uporabne površine segmenta.
- Skupina 43 %: ocenjena površina nad pragom v občini (model); letna prenova sorazmerno z državnim obsegom
  (vsaj 1,1 mio m² na leto 2026–2030 za 23,8 mio m² skupine, preglednica nacionalne trajektorije).
- Kurilno olje in plin: ocenjena raba 2023 (model) × državno razmerje po preglednici energentov (stanovanjski in storitveni sektor posebej).
- Minimalni standardi: nestanovanjske stavbe občine × delež nad pragom (izkaznice občine, sicer država), umerjeno na 16 % in 26 %.
"""
import re

import pandas as pd

from .draft import row
from .numbers import num

KWH_GWH = 1e6


def build(ctx, df: pd.DataFrame, res_b: pd.DataFrame, nres_b: pd.DataFrame, muni: dict, obc_idx: dict) -> dict:
    t22 = ctx.draft.table(r'Potrebni obseg prenov stavb za posamezne tipe')
    vol = {k: [num(c) * 1000 for c in row(t22, p)[2:4]] for k, p in
           (('hise', r'^Enodružinske'), ('bloki', r'^Večstanovanjske'), ('javne', r'^Stavbe javnega'), ('zasebne', r'^Stavbe zasebnega'))}
    t = ctx.draft.table(r'Nacionalna trajektorija prenove stanovanjskega fonda')
    wpb_row = row(t, r'^Prenova na leto')
    wpb_rate = float(re.findall(r'≥\s*(\d+,\d+)', wpb_row[2])[0].replace(',', '.'))
    wpb_nat = num(row(t, r'^Kumulativno prenovljen delež skupine 43')[0].split('(')[1].split('mio')[0])
    t30 = ctx.draft.table(r'Struktura končne rabe energije po energentih po scenariju NPS 2050')
    r30 = row
    ratio = {}
    for sec, off in (('res', 2), ('nres', 6)):
        for g, p in (('elko', r'^Ekstra lahko'), ('gas', r'^Zemeljski plin')):
            v = [num(c) for c in r30(t30, p)[off:off + 4]]
            ratio[(sec, g)] = [x / v[0] if v[0] else 0 for x in v[1:]]  # 2030, 2040, 2050 glede na 2023

    area = df.groupby(['obcina', 'seg']).m2.sum().unstack(fill_value=0)
    nat_area = area.sum()
    nres_n = df[df.seg.isin(['javne', 'zasebne'])].groupby('obcina').size()
    above = res_b.groupby('obcina').above.sum()
    car = {s: b.groupby('obcina')[['c_elko', 'c_gas']].sum() for s, b in (('res', res_b), ('nres', nres_b))}
    si_meps30, si_meps33 = obc_idx['si']['nres_above_meps30_pct'], obc_idx['si']['nres_above_meps33_pct']
    ctx.check(0.9 < wpb_rate < 1.3, f'cilji: državna letna prenova skupine 43 % ≥ {wpb_rate} mio m²')

    out = {}
    for eid, (sifra, _) in muni.items():
        a = area.loc[eid] if eid in area.index else pd.Series(0, index=nat_area.index)
        ren = {k: [round(v[i] * a.get(k, 0) / nat_area[k]) for i in range(2)] for k, v in vol.items()}
        wpb_m2 = float(above.get(eid, 0))
        fos = {}
        for g in ('elko', 'gas'):
            base = sum(float(car[s].loc[eid, f'c_{g}']) if eid in car[s].index else 0 for s in car)
            tgt = [sum((float(car[s].loc[eid, f'c_{g}']) if eid in car[s].index else 0) * ratio[(s, g)][i] for s in car) for i in range(3)]
            fos[g] = {'gwh_2023': round(base / KWH_GWH, 1), 'gwh': [round(x / KWH_GWH, 1) for x in tgt]}
        o = obc_idx['m'].get(sifra, {})
        p30 = o.get('nres_above_meps30_pct') if o.get('nres_above_meps30_pct') is not None else si_meps30
        p33 = o.get('nres_above_meps33_pct') if o.get('nres_above_meps33_pct') is not None else si_meps33
        n = int(nres_n.get(eid, 0))
        out[str(sifra)] = {
            'prenova_m2_leto': {k: {'2026_2030': v[0], '2031_2040': v[1]} for k, v in ren.items()},
            'prenova_skupaj_m2_leto': {'2026_2030': sum(v[0] for v in ren.values()), '2031_2040': sum(v[1] for v in ren.values())},
            'wpb': {'area_m2': round(wpb_m2), 'm2_leto_2026_2030': round(wpb_m2 * wpb_rate / wpb_nat), 'cum_pct': {'2030': 23, '2040': 65, '2050': 100}},
            'fosilna': fos,
            'meps': {'nres_buildings': n, 'n_2030': round(n * p30 / si_meps30 * 0.16), 'n_2033': round(n * p33 / si_meps33 * 0.26),
                     'local_ei': o.get('nres_above_meps30_pct') is not None},
        }
    return out
