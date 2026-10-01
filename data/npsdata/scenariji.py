"""Graf 3: raziskovalnik scenarijev.

Zavihek »Scenarij NPS 2050«: absolutne vrednosti 2023/2030/2040/2050 po sektorjih (pogl. 4.3–4.5).
Zavihek »Primerjava S0–S2«: indeksi iz primerjave strategij (pogl. 4.1.1) in 5-letne serije iz modela RenRates.
S2s (občutljivost) in alternativa DU-JE se ne objavita (odločitev 23. 9. 2026).
"""
import re

import openpyxl

from .context import Context, write_csv, write_json
from .draft import row
from . import enote
from .numbers import all_nums, num

SECTORS = [
    ('enodruzinske', 'Enodružinske stavbe', r'^Enodružinske'),
    ('vecstanovanjske', 'Večstanovanjske stavbe', r'^Večstanovanjske'),
    ('javne', 'Stavbe javnega sektorja', r'^Stavbe javnega'),
    ('zasebne', 'Stavbe zasebnega storitvenega sektorja', r'^Stavbe (zasebnega|ostalega)'),
    ('stanovanjski', 'Stanovanjski sektor skupaj', r'^Stanovanjski sektor skupaj'),
    ('storitveni', 'Storitveni sektor skupaj', r'^Storitveni sektor skupaj'),
    ('skupaj', 'Stavbe skupaj', r'^Stavbe skupaj$'),
]
YEARS = [2023, 2030, 2040, 2050]
SCEN = ['S0', 'S1', 'S2']


def _by_year(rows, pat, header):
    r = row(rows, pat)
    return [num(r[header.index(str(y))]) for y in YEARS]


def build(ctx: Context) -> dict:
    d = ctx.draft
    indicators = {}
    for key, cap, unit, sectors in [
        ('koncna_energija', r'Končna raba energije v stavbah v opazovanih letih', 'ktoe', SECTORS),
        ('primarna_energija', r'Primarna raba energije v stavbah po scenariju NPS 2050 \(obseg EPBD\), v ktoe, ter specifična', 'ktoe', SECTORS),
        ('emisije', r'Emisije toplogrednih plinov v stavbah v opazovanih letih', 'kt CO₂ ekv', SECTORS[4:]),
        ('ove', r'Obnovljivi viri energije v stavbah v opazovanih letih', '%', SECTORS[4:]),
    ]:
        t = d.table(cap)
        header = t[0]
        values = {sid: _by_year(t, pat, header) for sid, _, pat in sectors}
        for y_i, y in enumerate(YEARS):
            if len(sectors) == 7:
                parts = sum(values[s][y_i] for s in ('enodruzinske', 'vecstanovanjske', 'javne', 'zasebne'))
            else:
                parts = values['stanovanjski'][y_i] + values['storitveni'][y_i] if key != 'ove' else None
            if parts is not None:
                ctx.check_close(parts, values['skupaj'][y_i], f'{key} {y}: vsota sektorjev = skupaj', tol=1.5)
        indicators[key] = {'unit': unit, 'sectors': [s[0] for s in sectors], 'values': values}

    k = d.table(r'^Ključni cilji in kazalniki NPS 2050')
    for key, pat in [('koncna_energija', r'^Raba končne'), ('primarna_energija', r'^Raba primarne energije v stavbah, scenarij'),
                     ('emisije', r'^Emisije TGP'), ('ove', r'^Delež OVE')]:
        r = row(k, pat)
        for y, cell, ours in zip(YEARS, r[2:6], indicators[key]['values']['skupaj']):
            ctx.check_close(all_nums(cell)[0], round(ours), f'{key} {y}: preglednica 4.x = povzetek', tol=1)

    # ktoe → TWh (§11.12); vrednosti v ktoe ostanejo samo v CSV
    plan = {}
    for key, ind in indicators.items():
        if ind['unit'] == 'ktoe':
            plan[key] = ind['values']
            ind['values'] = {sid: [enote.twh(v) for v in vals] for sid, vals in ind['values'].items()}
            ind['unit'], ind['dec'] = 'TWh', enote.TWH_DEC
        else:
            ind['dec'] = 0 if key == 'emisije' else 1

    comparison = _comparison(ctx)

    data = {
        'meta': ctx.meta(
            [f'{d.name}: preglednice »Končna raba energije v stavbah v opazovanih letih«, »Primarna raba energije …«, '
             '»Emisije toplogrednih plinov …«, »Obnovljivi viri energije …« (pogl. 4.3–4.5)',
             f'{d.name}: preglednici »Opredelitev primerjanih strategij …« in »Rezultati primerjave strategij …« (pogl. 4.1.1)',
             'Model RenRates_SI, list Scenario_Compare (5-letne serije S0–S2)'],
            note='Primerjava S0–S2 je izražena v indeksih (2025 = 100), ker ima model RenRates drugačne absolutne vrednosti '
                 'kot projekcija NPS 2050. Primarna energija v zavihku NPS je pri faktorjih, veljavnih v posameznem letu (DU-OVE).'),
        'nps': {'years': YEARS, 'sectors': [{'id': s[0], 'name': s[1]} for s in SECTORS], 'indicators': indicators},
        'primerjava': comparison,
    }
    write_json('scenariji', data)
    write_csv('scenariji_nps', ['kazalnik', 'enota', 'sektor', *map(str, YEARS), *[f'{y} [ktoe]' for y in YEARS]],
              [[key, ind['unit'], dict((s[0], s[1]) for s in SECTORS)[sid], *vals, *(plan[key][sid] if key in plan else [None] * len(YEARS))]
               for key, ind in indicators.items() for sid, vals in ind['values'].items()])
    rows = []
    for key in ('fe_index', 'pe_res_fixed_index', 'worst_fg_share_pct'):
        ser = comparison[key]
        for s in SCEN:
            rows += [[key, s, y, v] for y, v in zip(ser['years'], ser[s])]
    write_csv('scenariji_primerjava', ['serija', 'scenarij', 'leto', 'vrednost'], rows)
    return data


def _comparison(ctx: Context) -> dict:
    d = ctx.draft
    t27 = d.table(r'Opredelitev primerjanih strategij spodbujanja prenov')
    names = t27[0][1:4]
    ctx.check([n[:2] for n in names] == SCEN, f'stolpci strategij so S0, S1, S2: {names}')
    t28 = d.table(r'Rezultati primerjave strategij spodbujanja prenov')
    ctx.check([c[:2] for c in t28[0][2:5]] == SCEN, f'stolpci rezultatov so S0, S1, S2: {t28[0]}')

    def three(pat):
        r = row(t28, pat)
        return r, r[2:5]  # S2s (stolpec 5) se izpusti

    fe = {s: [100] for s in SCEN}
    for y in (2030, 2040, 2050):
        _, cells = three(rf'^Končna raba energije {y} \(2025 = 100\)')
        for s, c in zip(SCEN, cells):
            fe[s].append(num(c))
    _, pe50 = three(r'^Primarna raba energije 2050 \(2025 = 100\)')
    _, fg = three(r'^Delež površine v razredih F in G')

    table = []
    for r in t28[1:]:
        table.append({'label': r[0], 'unit': r[1], 'values': dict(zip(SCEN, r[2:5]))})

    rr = _renrates(ctx)
    # Kontrola, da je model RenRates ista različica, kot jo povzema osnutek.
    for s, cells in zip(SCEN, fg):
        exp = all_nums(cells)  # '9,1 / 7,9 / 4,9' → 2030, 2035, 2050
        got = [round(rr['fg'][s][rr['years'].index(y)], 1) for y in (2030, 2035, 2050)]
        ctx.check(got == exp, f'RenRates {s} delež F+G 2030/2035/2050 = osnutek ({got} = {exp})')
    for y in (2030, 2035):
        _, cells = three(rf'^Povprečna primarna energija stanovanjskih stavb {y}, fiksni')
        for s, c in zip(SCEN, cells):
            ctx.check_close(round(rr['pe_idx'][s][rr['years'].index(y)] - 100, 1), num(c),
                            f'RenRates {s} primarna energija stanovanjskih {y} = osnutek', tol=0.05)
    for s in SCEN:
        for y_i, y in enumerate((2030, 2040, 2050), start=1):
            ctx.check_close(round(rr['fe_idx'][s][y]), fe[s][y_i], f'RenRates {s} končna energija {y} (indeks) = osnutek', tol=0)

    return {
        'scenarios': [{'id': s, 'name': n} for s, n in zip(SCEN, names)],
        'fe_index': {'years': [2025, 2030, 2040, 2050], **fe},
        'pe_index_2050': dict(zip(SCEN, [num(c) for c in pe50])),
        'pe_res_fixed_index': {'years': rr['years'], **{s: rr['pe_idx'][s] for s in SCEN}},
        'worst_fg_share_pct': {'years': rr['years'], **{s: rr['fg'][s] for s in SCEN}},
        'table': table,
    }


def _renrates(ctx: Context) -> dict:
    ws = openpyxl.load_workbook(ctx.files['renrates'], read_only=True, data_only=True)['Scenario_Compare']
    rows = [list(r) for r in ws.iter_rows(values_only=True)]

    def cols(header_first: str):
        hdr = next(r for r in rows if r[0] and str(r[0]).strip() == header_first and any(str(c or '').startswith('S0 –') for c in r))
        out = {}
        for s in SCEN:
            idx = [i for i, c in enumerate(hdr[:7]) if c and re.match(rf'^{s} –', str(c))]
            if len(idx) != 1:
                raise LookupError(f'RenRates Scenario_Compare: stolpec {s} v glavi »{header_first}« ni enoličen')
            out[s] = idx[0]
        return out

    def series(label: str, c: dict):
        pts = [(int(r[1]), {s: float(r[c[s]]) for s in SCEN}) for r in rows
               if r[0] and str(r[0]).strip() == label and re.fullmatch(r'\d{4}', str(r[1]).strip())]  # leto je zapisano kot besedilo
        if not pts:
            raise LookupError(f'RenRates Scenario_Compare: ni vrstic »{label}«')
        return pts

    c170 = cols('Kazalnik')
    pe = series('PE stanovanjske stavbe (SFH+MFH), fiksni faktorji', c170)
    fg = series('F+G', c170)
    years = [y for y, _ in pe]
    if years != [y for y, _ in fg] or years[0] != 2025:
        raise LookupError(f'RenRates: leta serij se ne ujemajo ({years})')

    c10 = cols('Indicator')
    fe_idx = {s: {} for s in SCEN}
    red = next(r for r in rows if r[0] and str(r[0]).strip() == 'Final energy reduction vs 2025')
    for s in SCEN:
        fe2050 = float(next(r for r in rows if r[0] == 'Final energy 2050 [GWh/yr]')[c10[s]])
        base = fe2050 / (1 - float(red[c10[s]]))
        for y in (2030, 2040, 2050):
            fe_idx[s][y] = 100 * float(next(r for r in rows if r[0] == f'Final energy {y} [GWh/yr]')[c10[s]]) / base

    return {
        'years': years,
        'pe_idx': {s: [round(100 * v[s] / pe[0][1][s], 1) for _, v in pe] for s in SCEN},
        'fg': {s: [round(100 * v[s], 1) for _, v in fg] for s in SCEN},
        'fe_idx': fe_idx,
    }
