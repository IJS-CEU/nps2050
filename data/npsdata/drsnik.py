"""11.3 Drsnik »Kaj pa, če«: kje pristane trajektorija stanovanjskih stavb pri drugačni stopnji prenove.

Vir: štirje zagoni modela RenRates_SI (RenRates_SI_drsnik_k070 … k200.xlsx ob RenRates_SI_NPS_scenariji.xlsx), ki se od
scenarija S2 razlikujejo samo v stopnjah prenove enostanovanjskih in večstanovanjskih stavb (3_Rates F6:J7, faktor 0,7–2,0).
Krivulje se ne interpolirajo in ne izmišljujejo (CLAUDE.md §11.3).

- Povprečna primarna energija stanovanjskih stavb pri fiksnih faktorjih 2025: energenti SFH + MFH (8_SFH_Charts) × faktorji PE
  2025 (7_Carriers) / stanovanjska površina; kot indeks (2025 = 100).
- kWh/(m²·a) na lestvici trajektorije NPS: trajektorija NPS × indeks položaja / indeks S2 (enako kot S0 in S1 v primerjavi strategij).
- Dosežena stopnja prenove: prenovljena stanovanjska površina 2026–2050 (delna, celovita, celovita s potresno) / površina / 25 let.
  Model prenavlja le stavbe razredov C–G, zato dosežena stopnja zaostaja za vpisano in se pri visokih stopnjah nasiči.
"""
import json

import openpyxl

from .context import OUT, Context, write_csv, write_json

POS = [('k070', 0.7), ('k100', 1.0), ('k150', 1.5), ('k200', 2.0)]
PERIODS = ['2026-2030', '2031-2035', '2036-2040', '2041-2045', '2046-2050']
YEARS = [2025, 2030, 2035, 2040, 2045, 2050]
CARRIER_ROWS = {'SFH': 147, 'MFH': 231}


def _run(path) -> dict:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rates = wb['3_Rates']
    rr = {i: r for i, r in enumerate(rates.iter_rows(min_row=1, max_row=70, max_col=10, values_only=True), start=1)}
    typ = {int(rr[i][0]): rr[i][3] for i in range(41, 71)}
    stock = {}
    for i in range(41, 71):
        stock[rr[i][3]] = stock.get(rr[i][3], 0) + (rr[i][2] or 0)
    res_area = stock['SFH'] + stock['MFH']
    ren = 0.0
    for per in PERIODS:
        ws = wb[per]
        rows = {i: r for i, r in enumerate(ws.iter_rows(min_row=1, max_row=110, max_col=32, values_only=True), start=1)}
        for rng, col in ((range(6, 36), 31), (range(42, 72), 28), (range(78, 108), 28)):  # delna AF, celovita AC, celovita + potresna AC
            for i in rng:
                if typ[int(rows[i][0])] in ('SFH', 'MFH'):
                    ren += rows[i][col] or 0
    ch = {i: r for i, r in enumerate(wb['8_SFH_Charts'].iter_rows(min_row=1, max_row=240, max_col=7, values_only=True), start=1)}
    car = wb['7_Carriers']
    pef = [car.cell(22 + j, 2).value for j in range(5)]
    pe = [sum(ch[CARRIER_ROWS[t] + j][1 + y] * pef[j] for t in CARRIER_ROWS for j in range(5)) * 1e6 / res_area for y in range(6)]
    co = {i: r for i, r in enumerate(wb['Class Overview'].iter_rows(min_row=1, max_row=156, max_col=7, values_only=True), start=1)}
    sc = {i: r for i, r in enumerate(wb['Scenario_Compare'].iter_rows(min_row=1, max_row=14, max_col=2, values_only=True), start=1)}
    return {
        'input_pct': {'SFH': [100 * v for v in rr[6][5:10]], 'MFH': [100 * v for v in rr[7][5:10]]},
        'rate_res_pct': 100 * ren / res_area / 25,
        'pe_fixed': pe,
        'fe_gwh': list(co[87][1:7]),
        'fe_2050_live': sc[14][1],
        'fg_pct': [100 * v for v in co[151][1:7]],
        'epbd_red': {'2030': co[142][2], '2035': co[143][2]},
    }


def build(ctx: Context) -> dict:
    base = ctx.files['renrates']
    runs = {}
    for k, f in POS:
        p = base.with_name(f'RenRates_SI_drsnik_{k}.xlsx')
        ctx.check(p.exists(), f'drsnik: datoteka {p.name}')
        runs[k] = _run(p)
    # k100 je scenarij S2: mora se ujemati z živim modelom v RenRates_SI_NPS_scenariji.xlsx
    s2 = openpyxl.load_workbook(base, read_only=True, data_only=True)['Scenario_Compare']
    fe50_s2 = next(r[1] for r in s2.iter_rows(min_row=12, max_row=20, max_col=2, values_only=True) if r[0] == 'Final energy 2050 [GWh/yr]')
    ctx.check(abs(runs['k100']['fe_2050_live'] - fe50_s2) < 0.01, f'drsnik: k100 = S2 (končna energija 2050 {runs["k100"]["fe_2050_live"]:.1f} = {fe50_s2:.1f} GWh)')
    ctx.check(all(runs[a]['fe_gwh'][5] > runs[b]['fe_gwh'][5] for (a, _), (b, _) in zip(POS, POS[1:])), 'drsnik: višja stopnja → nižja končna energija 2050')

    tr = json.loads((OUT / 'trajektorija.json').read_text(encoding='utf-8'))
    k = tr['kwh_m2']
    nps = dict(zip(k['years'], k['nps']))
    nps[2025] = round((nps[2020] + nps[2030]) / 2)
    epbd = {str(e['year']): e for e in k['epbd_max']}
    idx = {key: [100 * v / r['pe_fixed'][0] for v in r['pe_fixed']] for key, r in runs.items()}
    out = []
    for key, f in POS:
        r = runs[key]
        kwh = [nps[2020]] + [round(nps[y] * i / i2) for y, i, i2 in zip(YEARS, idx[key], idx['k100'])]
        out.append({
            'id': key, 'faktor': f,
            'stopnja_dosezena_pct': round(r['rate_res_pct'], 2),
            'stopnja_vpisana_2026_2030_pct': {t: round(v[0], 2) for t, v in r['input_pct'].items()},
            'kwh_m2': kwh,
            'indeks_pe': [round(v, 1) for v in idx[key]],
            'fe_twh': [round(v / 1000, 2) for v in r['fe_gwh']],
            'fe_zmanjsanje_2050_pct': round(100 * (1 - r['fe_gwh'][5] / r['fe_gwh'][0])),
            'fg_pct': [round(v, 1) for v in r['fg_pct']],
            'epbd_2030': kwh[2] <= epbd['2030']['max'], 'epbd_2035': kwh[3] <= epbd['2035']['max'],
        })
    ctx.check(out[1]['kwh_m2'][1:] == [nps[y] for y in YEARS], 'drsnik: položaj k100 = trajektorija NPS')
    data = {
        'meta': ctx.meta(['Model RenRates_SI (uskladitev z NEPN 2024, 3. 10. 2026): štirje zagoni z različnimi stopnjami prenove stanovanjskih stavb',
                          f'{ctx.draft.name}: nacionalna trajektorija stanovanjskega fonda in najvišje vrednosti po EPBD'],
                         note='kWh/(m²·a) na lestvici trajektorije NPS (trajektorija NPS × indeks položaja / indeks scenarija NPS). '
                              'Spreminjajo se samo stopnje prenove enostanovanjskih in večstanovanjskih stavb; vse drugo je kot v scenariju NPS 2050.'),
        'years': [2020] + YEARS, 'nps': [nps[2020]] + [nps[y] for y in YEARS], 'epbd_max': k['epbd_max'],
        'privzeto': 'k100', 'polozaji': out,
    }
    write_json('drsnik', data)
    write_csv('drsnik', ['položaj', 'faktor stopenj', 'dosežena stopnja prenove stanovanjskih stavb 2026–2050 [%/leto]']
              + [f'{y} [kWh/(m²·a)]' for y in data['years']] + ['končna energija 2050 [TWh, model]', 'zmanjšanje končne energije 2025–2050 [%]'],
              [[p['id'], p['faktor'], p['stopnja_dosezena_pct'], *p['kwh_m2'], p['fe_twh'][-1], p['fe_zmanjsanje_2050_pct']] for p in out])
    return data
