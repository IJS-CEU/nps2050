"""Trajektorija kot zgodba (CLAUDE.md §10.2): dopolni trajektorija.json s pasovi razredov, skupino 43 %,
primerjavo strategij S0–S2 v kWh/(m²·a) in cilji kot odstotek glede na 2020 in 2023.

- Pasovi razredov: meje razredov NPS za hiše in bloke, tehtane po uporabni površini (okvirno za povprečno stanovanjsko stavbo).
- S0 in S1 v kWh/(m²·a): trajektorija NPS × (indeks strategije / indeks S2) iz primerjave strategij (pogl. 4.1.1);
  leto 2025 je linearno med 2020 in 2030.
- Odstotki glede na 2020 so izpeljani (izhodiščna preglednica 2020 in cilji iz preglednice ključnih ciljev); osnutek jih navaja le glede na 2023.
"""
import json

import numpy as np

from .context import OUT, Context, write_csv
from .draft import row
from . import enote
from .numbers import lead, num

BOUNDS = ['A|B', 'B|C', 'C|D', 'D|E', 'E|F', 'F|G']


def build(ctx: Context) -> dict:
    tr = json.loads((OUT / 'trajektorija.json').read_text(encoding='utf-8'))
    sf = json.loads((OUT / 'stavbni_fond.json').read_text(encoding='utf-8'))
    sc = json.loads((OUT / 'scenariji.json').read_text(encoding='utf-8'))
    kz = json.loads((OUT / 'kazalniki.json').read_text(encoding='utf-8'))
    cats = {c['id']: c for c in sf['categories']}
    h, b = cats['HISA'], cats['BLOKI']
    wa, wb = h['area_mio_m2'], b['area_mio_m2']
    bands = {k: round((h['class_bounds'][k] * wa + b['class_bounds'][k] * wb) / (wa + wb)) for k in BOUNDS}
    ctx.check(bands['A|B'] == 75, 'trajektorija: meja A|B tehtano = 75 kWh/(m²·a)')

    # skupina 43 %: površina in povprečna raba nad pragom (tehtano po površini skupine)
    ga = h['worst_43']['area_share_pct'] / 100 * wa, b['worst_43']['area_share_pct'] / 100 * wb
    wpb_avg = round((h['worst_43']['avg_pe_above'] * ga[0] + b['worst_43']['avg_pe_above'] * ga[1]) / sum(ga))
    t = ctx.draft.table(r'Nacionalna trajektorija prenove stanovanjskega fonda')
    cum = [num(c) if c.strip() not in ('–', '') else None for c in row(t, r'^Kumulativno prenovljen delež skupine 43')[1:]]
    wpb_area = num(row(t, r'^Kumulativno prenovljen delež skupine 43')[0].split('(')[1].split('mio')[0])
    ctx.check(abs(sum(ga) - wpb_area) / wpb_area < 0.05, f'trajektorija: površina skupine 43 % {sum(ga):.1f} ≈ osnutek {wpb_area} mio m²')

    # strategije v kWh/(m²·a)
    k = tr['kwh_m2']
    ix = sc['primerjava']['pe_res_fixed_index']
    nps = dict(zip(k['years'], k['nps']))
    nps[2025] = round((nps[2020] + nps[2030]) / 2)
    scen = {}
    for s in ('S0', 'S1', 'S2'):
        vals = []
        for y, i_s, i2 in zip(ix['years'], ix[s], ix['S2']):
            vals.append(round(nps[y] * i_s / i2))
        scen[s] = [nps[2020]] + vals
    years_s = [2020] + ix['years']
    ctx.check(scen['S2'][1:] == [nps[y] for y in ix['years']], 'trajektorija: S2 = trajektorija NPS')

    # cilji glede na 2020 in 2023
    t14 = ctx.draft.table(r'Končna in primarna raba energije po segmentih stavb v izhodiščnih letih')
    base2020 = {'koncna_energija': num(row(t14, r'^Stavbe skupaj')[1]), 'primarna_energija': num(row(t14, r'^Stavbe skupaj')[3]), 'emisije': None}
    items = {i['id']: i for i in kz['items']}
    cilji = []
    for iid, label, unit in [('koncna_energija', 'Končna energija v stavbah', 'TWh'), ('primarna_energija', 'Primarna energija v stavbah', 'TWh'),
                             ('emisije', 'Emisije TGP iz stavb', 'kt CO₂ ekv.')]:
        it = items[iid]
        # odstotki iz vrednosti v enotah načrta (ktoe), prikaz v TWh (§11.12)
        if 'plan' in it:
            b23, vals = it['plan']['baseline'], dict(zip([v['year'] for v in it['values']], it['plan']['values']))
            conv, dec = enote.twh, enote.TWH_DEC
        else:
            b23, vals = it['baseline']['value'], {v['year']: lead(v['text']) for v in it['values']}
            conv, dec = (lambda x: x), 0
        b20 = base2020[iid]
        cilji.append({'id': iid, 'label': label, 'unit': unit, 'dec': dec, 'base2020': conv(b20), 'base2023': conv(b23),
                      'plan': {'base2020': b20, 'base2023': b23, 'years': {str(y): v for y, v in vals.items()}},
                      'years': {str(y): {'value': conv(v), 'vs2023': round(100 * (v / b23 - 1)), 'vs2020': round(100 * (v / b20 - 1)) if b20 else None} for y, v in vals.items()}})

    tr['zgodba'] = {
        'bands': bands, 'wpb': {'area_mio_m2': wpb_area, 'avg_pe_2020': wpb_avg, 'target_bc': bands['B|C'],
                                'years': [2030, 2035, 2040, 2045, 2050], 'renovated_pct': [c for c in cum if c is not None]},
        'scenarios': {'years': years_s, **scen, 'names': {s['id']: s['name'] for s in sc['primerjava']['scenarios']}},
        'cilji': cilji,
        'note': 'Pasovi razredov: meje za hiše in bloke, tehtane po uporabni površini. S0 in S1 preračunana iz indeksov primerjave strategij '
                '(trajektorija NPS × indeks strategije / indeks S2). Odstotki glede na 2020 izpeljani iz izhodiščne preglednice 2020.',
    }
    (OUT / 'trajektorija.json').write_text(json.dumps(tr, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    write_csv('trajektorija_strategije', ['leto', 'S0 [kWh/(m²·a)]', 'S1 [kWh/(m²·a)]', 'S2 – scenarij NPS 2050 [kWh/(m²·a)]'],
              [[y, a, b_, c] for y, a, b_, c in zip(years_s, scen['S0'], scen['S1'], scen['S2'])])
    write_csv('cilji_2020_2023', ['kazalnik', 'enota', 'izhodišče 2020', 'izhodišče 2023'] + [f'{y}: vrednost / glede na 2020 [%] / glede na 2023 [%]' for y in (2030, 2040, 2050)]
              + ['izhodišče 2020 [ktoe]', 'izhodišče 2023 [ktoe]', '2030 [ktoe]', '2040 [ktoe]', '2050 [ktoe]'],
              [[c['label'], c['unit'], c['base2020'], c['base2023']] + [f"{c['years'][str(y)]['value']} / {c['years'][str(y)]['vs2020']} / {c['years'][str(y)]['vs2023']}" for y in (2030, 2040, 2050)]
               + ([c['plan']['base2020'], c['plan']['base2023'], *[c['plan']['years'][str(y)] for y in (2030, 2040, 2050)]] if c['unit'] == 'TWh' else [None] * 5) for c in cilji])
    for c in cilji:
        del c['plan']
    return tr
