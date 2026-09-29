"""Spremljanje (CLAUDE.md §10.4): letni kazalniki iz registrov, izhodišče 2026. Vsako leto se doda ena vrstica z isto metodo.

- Energetske izkaznice: veljavne na dan izvoza, izdane po letih (register izkaznic), pokritost in razredi (iz obcine.py).
- Pregledi klimatskih sistemov: izdana poročila po letih in stavbe (KLIMSIS; leto poročila = DATE_CREATED).
- Eko sklad: stavbe s prvo podprto naložbo posamezne vrste po letih (matrika ukrepov do 2024 in poročilo 2025).
"""
import json

import pandas as pd

from .context import OUT, Context, write_csv, write_json
from .stavbe import ES_GROUPS, build_table

YEARS = list(range(2017, 2027))
ES_YEARS = range(2017, 2026)  # v matriki Eko sklada so pred letom 2017 pri nekaterih vrstah ukrepov vrzeli
ES_NAMES = {'ovoj': 'izolacija ovoja', 'okna': 'zamenjava oken', 'tc': 'toplotna črpalka', 'biomasa': 'kurilna naprava na lesno biomaso',
            'daljinsko': 'daljinsko ogrevanje', 'pv': 'sončna elektrarna', 'prezr': 'prezračevanje z vračanjem toplote'}


def build(ctx: Context) -> dict:
    B = ctx.files['ei_stanje'].parent
    ei = pd.read_csv(B / 'EI_izkaznice.csv', sep='|', dtype=str, usecols=['STATUS', 'TIP', 'DATUM_IZDELAVE', 'DELETED'])
    ei = ei[(ei.DELETED != 'D') & ~ei.STATUS.isin(['ZBRISANO', 'V_DELU'])]
    ei['y'] = pd.to_datetime(ei.DATUM_IZDELAVE, dayfirst=True, errors='coerce').dt.year
    issued = ei[ei.y.isin(YEARS)].groupby(['y', 'TIP']).size().unstack(fill_value=0)
    st = pd.read_csv(ctx.files['ei_stanje'], sep='|', dtype=str)
    tip = st['Tip izkaznice'].str.strip()
    valid = {'skupaj': int(len(st)), 'racunske': int((tip == 'računska').sum()), 'merjene': int((tip == 'merjena').sum())}
    ctx.check(valid['skupaj'] > 80000, f'spremljanje: veljavnih izkaznic {valid["skupaj"]}')

    ks = pd.read_csv(ctx.files['klimsis'], sep='|', dtype=str)
    ks = ks[ks.KS_STATUS == 'IZDANO'].copy()
    ks['y'] = pd.to_datetime(ks.DATE_CREATED, dayfirst=True, errors='coerce').dt.year
    kst = pd.read_csv(ctx.files['klimsis'].parent / 'KS_porocila_stavbe.csv', sep='|', dtype=str)
    kst = kst[kst.KSPR_ID.isin(set(ks.KSPR_ID))]
    n_bld = int((kst.SIF_KO.str.strip() + '-' + kst.STA_SID.str.strip()).nunique())
    ks_year = ks.groupby('y').size().reindex(range(2020, 2027), fill_value=0)
    ctx.check(n_bld >= 190, f'spremljanje: stavb s poročilom KLIMSIS {n_bld} (osnutek: 200)')
    ctx.check(len(ks) == 648, f'spremljanje: izdanih poročil KLIMSIS {len(ks)} = osnutek (648)')
    nam = ks.STAVBA_NAMEMBNOST.fillna('').str.replace('\x9e', 'ž').str.replace('_', ' ').str.strip()
    ks_nam = nam.value_counts()

    df = build_table(ctx)
    es = {}
    for g in ES_GROUPS:
        yrs = pd.to_numeric(df[f'es_{g}'], errors='coerce')
        es[g] = yrs.value_counts().reindex(ES_YEARS, fill_value=0).astype(int).tolist()

    ix = json.loads((OUT / 'obcine_index.json').read_text(encoding='utf-8'))
    si = ix['si']
    data = {
        'meta': ctx.meta(['Register energetskih izkaznic (izvoz 28. 9. 2026)', 'Register poročil o pregledih klimatskih sistemov KLIMSIS (izvoz 28. 9. 2026)',
                          'Eko sklad: podprte naložbe po stavbah do 2025', 'Kataster nepremičnin GURS (30. 8. 2026)'],
                         note='Izhodišče 2026; od leta 2027 se doda ena vrstica na leto z isto metodo. Leto 2026 je delno (do dneva izvoza).'),
        'stanje': '28. 9. 2026',
        'ei': {'valid': valid, 'issued': {'years': YEARS, 'REI': [int(issued.get('REI', pd.Series()).get(y, 0)) for y in YEARS],
                                          'MEI': [int(issued.get('MEI', pd.Series()).get(y, 0)) for y in YEARS]},
               'coverage': {s: {'buildings_pct': si['segments'][s]['ei_buildings_pct'], 'area_pct': si['segments'][s]['ei_area_pct']} for s in ('hise', 'bloki', 'javne', 'zasebne')},
               'classes': {s: si['segments'][s]['classes_pct'] for s in ('hise', 'bloki', 'javne', 'zasebne')},
               'ei_calc': {s: si['segments'][s]['ei_calc'] for s in ('hise', 'bloki', 'javne', 'zasebne')}},
        'klimsis': {'years': list(range(2020, 2027)), 'reports': ks_year.astype(int).tolist(), 'total': int(len(ks)), 'buildings': n_bld,
                    'by_use': [{'name': k, 'n': int(v)} for k, v in ks_nam.head(8).items()]},
        'eko_sklad': {'years': list(ES_YEARS), 'groups': [{'id': g, 'name': ES_NAMES[g], 'buildings': es[g]} for g in ES_GROUPS if g != 'daljinsko']},
    }
    write_json('spremljanje', data)
    write_csv('spremljanje_izkaznice', ['leto', 'izdane računske izkaznice', 'izdane merjene izkaznice'],
              [[y, a, b] for y, a, b in zip(YEARS, data['ei']['issued']['REI'], data['ei']['issued']['MEI'])])
    write_csv('spremljanje_klimsis', ['leto', 'izdana poročila o pregledu klimatskih sistemov'], list(map(list, zip(data['klimsis']['years'], data['klimsis']['reports']))))
    write_csv('spremljanje_eko_sklad', ['leto'] + [g['name'] for g in data['eko_sklad']['groups']],
              [[y] + [g['buildings'][i] for g in data['eko_sklad']['groups']] for i, y in enumerate(data['eko_sklad']['years'])])
    return data
