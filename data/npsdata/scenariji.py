"""Graf 3: raziskovalnik scenarijev.

Zavihek »Scenarij NPS 2050«: absolutne vrednosti 2023/2030/2040/2050 po sektorjih (pogl. 4.3–4.5).
Zavihek »Primerjava S0–S2«: indeksi iz primerjave strategij (pogl. 4.1.1) in 5-letne serije iz modela RenRates.
S2s (občutljivost) in alternativa DU-JE se ne objavita (odločitev 23. 9. 2026).
"""
import re

import openpyxl

from .context import Context, write_csv, write_json
from .draft import row
from .drsnik import BASE_2020, OCENA_2025
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


def _fmt(v, dec=0, sign=False):
    t = f'{abs(v):,.{dec}f}'.replace(',', ' ').replace('.', ',').replace(' ', '.')
    return ('−' if v < 0 else ('+' if sign and v > 0 else '')) + t


ROW_EPBD = ('Povprečna primarna energija stanovanjskih stavb 2030, fiksni faktorji (zahteva EPBD −16 %)',
            'Povprečna primarna energija stanovanjskih stavb 2035, fiksni faktorji (zahteva −20 do −22 %)')
# vrstice osnutka, ki jih stran prikazuje z drugačno osnovo (osnutek: glede na 2025; EPBD: glede na 2020)
ALIAS = {}


def _comparison(ctx: Context) -> dict:
    """Primerjava S0–S2 iz modela RenRates (Scenario_Compare). Model je novejši od preglednice v osnutku (pogl. 4.1.1):
    po uskladitvi z NEPN 2024 (3. 10. 2026) gredo na stran vrednosti modela, neskladja z osnutkom pa se javijo avtorjem."""
    d = ctx.draft
    t27 = d.table(r'Opredelitev primerjanih strategij spodbujanja prenov')
    names = t27[0][1:4]
    ctx.check([n[:2] for n in names] == SCEN, f'stolpci strategij so S0, S1, S2: {names}')
    t28 = d.table(r'Rezultati primerjave strategij spodbujanja prenov')
    ctx.check([c[:2] for c in t28[0][2:5]] == SCEN, f'stolpci rezultatov so S0, S1, S2: {t28[0]}')

    rr = _renrates(ctx)
    m = rr['m']
    fe = {s: [100] + [round(rr['fe_idx'][s][y]) for y in (2030, 2040, 2050)] for s in SCEN}
    pe50 = {s: round(100 * (1 - m[s]['pe_red'])) for s in SCEN}
    yi = rr['years'].index
    rows = [
        ('Končna raba energije 2030 (2025 = 100)', 'indeks', lambda s: str(fe[s][1])),
        ('Končna raba energije 2040 (2025 = 100)', 'indeks', lambda s: str(fe[s][2])),
        ('Končna raba energije 2050 (2025 = 100)', 'indeks', lambda s: str(fe[s][3])),
        ('Primarna raba energije 2050 (2025 = 100)', 'indeks', lambda s: str(pe50[s])),
        ('Emisije CO₂ 2050 pri zamrznjenih faktorjih 2025 (učinek prenov)', '% glede na 2025', lambda s: _fmt(-100 * m[s]['co2_frozen_red'])),
        ('Kumulativna končna raba 2025–2050', 'TWh', lambda s: _fmt(m[s]['cum_fe'])),
        # EPBD meri zmanjšanje glede na 2020 (osnutek v tej vrstici navaja zmanjšanje glede na 2025): ocenjeno stanje 2025 × indeks
        # modela, kot v drsniku (drsnik.py)
        (ROW_EPBD[0], '% glede na 2020', lambda s: _fmt(100 * (round(OCENA_2025['osrednja'] * rr['pe_idx_raw'][s][yi(2030)] / 100) / BASE_2020 - 1), 1)),
        (ROW_EPBD[1], '% glede na 2020', lambda s: _fmt(100 * (round(OCENA_2025['osrednja'] * rr['pe_idx_raw'][s][yi(2035)] / 100) / BASE_2020 - 1), 1)),
        ('Delež površine v razredih F in G 2030 / 2035 / 2050', '%', lambda s: ' / '.join(_fmt(rr['fg'][s][yi(y)], 1) for y in (2030, 2035, 2050))),
        ('Površina v razredu A leta 2050', 'mio m²', lambda s: _fmt(m[s]['class_a_2050'], 1)),
        ('Prenovljena površina 2026–2050 (od tega celovito)', 'mio m²', lambda s: f"{_fmt(m[s]['renovated'], 1)} ({_fmt(m[s]['deep'], 1)})"),
        ('Povprečna dosežena letna stopnja prenove 2026–2050', '% fonda', lambda s: _fmt(m[s]['rate'], 2)),
        ('Investicije 2026–2050 (od tega 2026–2030)', 'mrd €', lambda s: f"{_fmt(m[s]['inv'], 1)} ({_fmt(m[s]['inv_2030'], 1)})"),
        ('Javna nepovratna sredstva 2026–2050', 'mrd €', lambda s: _fmt(m[s]['public'], 2)),
        ('Investicija na enoto prihranka končne energije 2050', 'mio € na GWh/leto', lambda s: _fmt(m[s]['inv_per_gwh'], 2)),
        ('Izpolnjeni mejniki (od 12)', 'št.', lambda s: str(int(m[s]['met']))),
    ]
    table = [{'label': lab, 'unit': u, 'values': {s: f(s) for s in SCEN}} for lab, u, f in rows]

    # Neskladja z osnutkom (preglednica »Rezultati primerjave strategij«) – za avtorje; na stran gre model.
    for r in t28[1:]:
        ours = next((t for t in table if t['label'] == ALIAS.get(r[0], r[0])), None)
        if ours is None:
            ctx.warnings.append(f'primerjava strategij: vrstice »{r[0]}« ni v izračunu iz modela')
            continue
        same = [str(c).strip() for c in r[2:5]] == [ours['values'][s] for s in SCEN]
        ctx.warn_unless(same, f'primerjava strategij »{r[0]}«: osnutek {r[2:5]} ≠ model RenRates (NEPN 2024) '
                              f'{[ours["values"][s] for s in SCEN]}')

    return {
        'scenarios': [{'id': s, 'name': n} for s, n in zip(SCEN, names)],
        'fe_index': {'years': [2025, 2030, 2040, 2050], **fe},
        'pe_index_2050': pe50,
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

    def val(label, c, s, year=None):
        for r in rows:
            if r[0] and str(r[0]).strip() == label and (year is None or str(r[1]).strip() == str(year)):
                return float(r[c[s]])
        raise LookupError(f'RenRates Scenario_Compare: ni vrstice »{label}« {year or ""}')

    hdr154 = next(r for r in rows if r[0] == 'Period')  # vrstica 155: B = S0, C = S1, D = S2, E = S2s
    c154 = {s: [i for i, c in enumerate(hdr154[:6]) if c and re.match(rf'^{s} –', str(c))][0] for s in SCEN}
    c77 = cols('Indicator')
    m = {}
    for s in SCEN:
        m[s] = {
            'pe_red': val('Primary energy reduction vs 2025', c10, s),
            'co2_frozen_red': val('CO₂ reduction vs 2025 at frozen factors', c10, s),
            'cum_fe': val('Cumulative final energy 2025–2050 [TWh]', c10, s),
            'met': val('Targets met (of 12)', c10, s),
            'rate': val('Povprečna letna stopnja prenove, dosežena 2026–2050 [%/leto celotnega fonda]', cols('Parameter'), s),
            'renovated': val('Renovated floor area 2026–2050 [mio m²]', c77, s),
            'deep': val('… of which deep [mio m²]', c77, s),
            'inv_per_gwh': val('Cost per unit of 2050 final-energy saving [mio EUR per GWh/yr]', c77, s),
            'inv': val('TOTAL investment [bn EUR2025] (brez eskalacije gradbenih stroškov)', c154, s),
            'inv_2030': val('2026-2030', c154, s),
            'public': val('javna sredstva skupaj 2026–2050', c170, s, 'mrd €'),
            'class_a_2050': val('razred A', c170, s, 2050),
        }
    return {
        'm': m,
        'years': years,
        'pe_idx': {s: [round(100 * v[s] / pe[0][1][s], 1) for _, v in pe] for s in SCEN},
        'pe_idx_raw': {s: [100 * v[s] / pe[0][1][s] for _, v in pe] for s in SCEN},
        'fg': {s: [round(100 * v[s], 1) for _, v in fg] for s in SCEN},
        'fe_idx': fe_idx,
    }
