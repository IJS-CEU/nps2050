"""Sankey: prehodi stanovanjskih stavb med razredi primarne energije po scenariju NPS 2050 (S2), 2025–2050.

Vir: model RenRates_SI, list Sankey_export (kot sliki v pogl. 4.1.1 osnutka). Širina toka je primarna energija
stavb v razredu [GWh/leto], ne površina. Za javne in storitvene stavbe list tokov nima, zato sta le SFH in MFH.
"""
import re
from collections import defaultdict

import openpyxl

from .context import Context, write_csv, write_json

CLASSES = ['A1', 'A2', 'B1', 'B2', 'C', 'D', 'E', 'F', 'G']
TYPES = {'SFH': ('enostanovanjske', 'Enostanovanjske hiše'), 'MFH': ('vecstanovanjske', 'Večstanovanjske stavbe')}
EPS = 1e-6  # numerični ostanki modela (npr. 4e-15, −6e-15) so ničla


def _node(s: str) -> tuple[str, int]:
    m = re.fullmatch(r'\s*([A-G][12]?)\s+(\d{4})\s*', str(s))
    if not m or m.group(1) not in CLASSES:
        raise ValueError(f'Sankey_export: neznano vozlišče {s!r}')
    return m.group(1), int(m.group(2))


def build(ctx: Context) -> dict:
    ws = openpyxl.load_workbook(ctx.files['renrates'], read_only=True, data_only=True)['Sankey_export']
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    header = next(r for r in rows if r and r[0] == 'Source')
    out, csv_rows = {}, []
    for code, (key, name) in TYPES.items():
        col = next((i for i, h in enumerate(header) if h == f'Value_GWh_{code}'), None)
        if col is None:
            raise LookupError(f'Sankey_export: ni stolpca Value_GWh_{code}')
        links = []
        start = rows.index(header) + 1
        for r in rows[start:]:
            src, tgt, val = r[col - 2], r[col - 1], r[col]
            if src is None or tgt is None or val is None:
                continue
            v = float(val)
            if v < -EPS:
                raise ValueError(f'{code}: negativen tok {src} → {tgt} = {v}')
            if v <= EPS:
                continue
            (cs, ys), (ct, yt) = _node(src), _node(tgt)
            ctx.check(yt == ys + 5, f'{code}: tok {src} → {tgt} je 5-letni korak')
            links.append({'source': f'{cs} {ys}', 'target': f'{ct} {yt}', 'value': round(v, 2)})
        years = sorted({int(l['source'][-4:]) for l in links} | {int(l['target'][-4:]) for l in links})

        # Tok iz leta y v y+5 nosi primarno energijo stavb v letu y (ob začetku koraka). Zato se ohranja vsota
        # posameznega koraka (odtok leta y = dotok leta y+5), vozlišča pa se z vsako prenovo ožijo.
        inflow, outflow = defaultdict(float), defaultdict(float)
        for l in links:
            outflow[l['source']] += l['value']
            inflow[l['target']] += l['value']
        yr_out = {y: sum(v for n, v in outflow.items() if n.endswith(str(y))) for y in years}
        yr_in = {y: sum(v for n, v in inflow.items() if n.endswith(str(y))) for y in years}
        for y in years[:-1]:
            ctx.check_close(yr_out[y], yr_in[y + 5], f'{code}: korak {y}→{y + 5} ohranja energijo', tol=0.5)
        for a_, b_ in zip(years[:-2], years[1:-1]):
            ctx.check(yr_out[b_] <= yr_out[a_] + 0.5, f'{code}: primarna energija ne narašča ({a_}: {yr_out[a_]:.0f}, {b_}: {yr_out[b_]:.0f})')
        downgrades = [l for l in links if CLASSES.index(l['target'].split()[0]) > CLASSES.index(l['source'].split()[0])]
        ctx.warn_unless(not downgrades, f'{code}: tokovi v slabši razred: {downgrades[:3]}')

        # Vrednost vozlišča = primarna energija razreda v tem letu (odtok). Zadnje leto nima odtoka, zato dotok,
        # ki je energija teh stavb ob stanju predhodnega koraka (to je navedeno v opisu grafa).
        last = years[-1]
        nodes = []
        for y in years:
            for c in CLASSES:
                n = f'{c} {y}'
                v = outflow[n] if y != last else inflow[n]
                if v > EPS:
                    nodes.append({'name': n, 'class': c, 'year': y, 'value': round(v, 1)})
        totals = {y: round(yr_out[y] if y != last else yr_in[y], 1) for y in years}
        out[key] = {'name': name, 'years': years, 'nodes': nodes, 'links': links, 'totals': totals}
        csv_rows += [[name, l['source'].split()[1], l['source'].split()[0], l['target'].split()[1], l['target'].split()[0], l['value']] for l in links]

    data = {
        'meta': ctx.meta(['Model RenRates_SI, list Sankey_export (scenarij NPS 2050, S2), prikazan v pogl. 4.1.1 osnutka'],
                         note='Vrednosti so primarna energija stavb v razredu [GWh/leto], ne površina. Razredi po lestvici '
                              'primarne energije (A1–G). Tokovi pod 1e-6 GWh (numerični ostanki) so izpuščeni.'),
        'classes': CLASSES,
        'types': out,
    }
    write_json('sankey', data)
    write_csv('sankey_prehodi', ['vrsta stavb', 'iz leta', 'iz razreda', 'v leto', 'v razred', 'primarna energija [GWh/leto]'], csv_rows)
    return data
