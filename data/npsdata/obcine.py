"""Moja občina (CLAUDE.md §10.1): izmerjeni kazalniki po občinah iz katastra, registra izkaznic in Eko sklada.

Objavijo se samo agregati. Celice z manj kot MIN_CELL stavbami so null; deleži in razvrstitve po razredih se
izračunajo le, če imenovalec obsega vsaj MIN_CELL stavb. Razredi se določijo iz primarne energije računskih
izkaznic po mejah razredov NPS 2050 za kategorijo stavbe (stavbni_fond.json).
"""
import json

import numpy as np
import pandas as pd

from .context import OUT, Context, write_csv, write_json
from .stavbe import ES_GROUPS, PERIODS, build_table
from .stavbni_fond import CATS, MIN_CELL, MIN_EI

# Priklop na daljinsko ogrevanje ima v podatkih Eko sklada le okoli 60 stanovanjskih stavb, zato se ne prikazuje.
ES_SHOW = [k for k in ES_GROUPS if k != 'daljinsko']

SEGS = [('hise', 'Enostanovanjske hiše'), ('bloki', 'Večstanovanjske stavbe'), ('javne', 'Javne stavbe'),
        ('zasebne', 'Stavbe zasebnega storitvenega sektorja')]
CLS = ['A', 'B', 'C', 'D', 'E', 'F', 'G']
GROUPS = {'A–C': ['A', 'B', 'C'], 'D–E': ['D', 'E'], 'F–G': ['F', 'G']}
BOUNDS = ['A|B', 'B|C', 'C|D', 'D|E', 'E|F', 'F|G']
ES_NAMES = {'ovoj': 'izolacija ovoja', 'okna': 'zamenjava oken', 'tc': 'toplotna črpalka', 'biomasa': 'kurilna naprava na lesno biomaso',
            'daljinsko': 'priklop na daljinsko ogrevanje', 'pv': 'sončna elektrarna', 'prezr': 'prezračevanje z vračanjem toplote'}


def _n(v: int):
    return None if 0 < v < MIN_CELL else int(v)


def _pct(num: float, den: float, n_den: int, n_num: int | None = None, dec: int = 1):
    """Delež le, če imenovalec obsega vsaj MIN_CELL stavb in števec ni majhna celica (1–9 stavb), sicer bi se dalo izračunati skrito število."""
    if n_den < MIN_CELL or den <= 0:
        return None
    if n_num is not None and (0 < n_num < MIN_CELL or 0 < n_den - n_num < MIN_CELL):
        return None  # majhen števec ali majhen komplement
    return round(100 * num / den, dec)


def _classify(df: pd.DataFrame, fond: dict) -> pd.Series:
    """Razred A–G iz primarne energije računske izkaznice po mejah za kategorijo stavbe; brez izkaznice NaN."""
    out = pd.Series(np.nan, index=df.index, dtype=object)
    for c in fond['categories']:
        m = (df.cat == c['id']) & df.ei_pe.notna()
        edges = [-np.inf] + [c['class_bounds'][b] for b in BOUNDS] + [np.inf]
        out[m] = pd.cut(df.loc[m, 'ei_pe'], edges, labels=CLS, right=True).astype(str)
    return out


def _flags(df: pd.DataFrame, fond: dict) -> pd.DataFrame:
    thr43 = {c['id']: c['worst_43']['threshold'] for c in fond['categories'] if c.get('worst_43')}
    meps = {c['id']: c['meps'] for c in fond['categories'] if c.get('meps')}
    df['above43'] = df.cat.map(thr43).lt(df.ei_pe) & df.ei_pe.notna()
    df['above_meps30'] = df.cat.map({k: v['threshold_2030'] for k, v in meps.items()}).lt(df.ei_pe) & df.ei_pe.notna()
    df['above_meps33'] = df.cat.map({k: v['threshold_2033'] for k, v in meps.items()}).lt(df.ei_pe) & df.ei_pe.notna()
    for c in ('obnova_streha', 'obnova_fasada', 'obnova_okna'):
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df['obnova_any'] = df[['obnova_streha', 'obnova_fasada', 'obnova_okna']].notna().any(axis=1)
    return df


def _segment(g: pd.DataFrame) -> dict:
    n, a = len(g), g.m2.sum()
    e = g[g.ei_any]
    c = g[g.cls.notna()]
    cnt = {k: int((c.cls == k).sum()) for k in CLS}
    # razvrstitev le pri vsaj MIN_CELL izkaznicah in če ima vsak zaseden razred vsaj MIN_CELL stavb
    # (sicer bi se skrito število izračunalo iz ostalih razredov)
    ok = len(c) >= MIN_EI
    # sicer združeno v tri skupine (A–C, D–E, F–G), če so te dovolj velike
    gcnt = {g: sum(cnt[k] for k in ks) for g, ks in GROUPS.items()}
    ok_g = False
    d = {
        'buildings': _n(n),
        'area_k_m2': round(a / 1e3, 1) if n >= MIN_CELL else None,
        'ei_buildings_pct': _pct(len(e), n, n, len(e)),
        'ei_area_pct': _pct(e.m2.sum(), a, n, len(e)),
        'ei_calc': _n(len(c)),
        'classes_pct': {k: round(100 * cnt[k] / len(c), 1) for k in CLS} if ok else None,
        'class_groups_pct': {g: round(100 * v / len(c), 1) for g, v in gcnt.items()} if ok_g else None,
    }
    return d


def _area(g: pd.DataFrame) -> dict:
    """Kazalniki za območje (občina ali Slovenija)."""
    res = g[g.seg.isin(['hise', 'bloki'])]
    nres = g[g.seg.isin(['javne', 'zasebne'])]
    rc = res[res.cls.notna()]
    nc = nres[nres.ei_pe.notna() & nres.cat.isin([c[0] for c in CATS[2:]])]
    out = {
        'buildings': int(len(g)), 'area_k_m2': round(g.m2.sum() / 1e3, 1),
        'segments': {s: _segment(g[g.seg == s]) for s, _ in SEGS},
        'res_period_area_pct': {p: _pct(res.loc[res.period == p, 'm2'].sum(), res.m2.sum(), len(res), int((res.period == p).sum())) for p in PERIODS},
        # Delež stanovanjskih stavb z izkaznico nad pragom 43 % (vzorec izkaznic – informativno)
        'res_above43_pct': round(100 * rc.above43.mean(), 1) if len(rc) >= MIN_EI else None,
        'res_ei_calc': int(len(rc)),
        'nres_above_meps30_pct': round(100 * nc.above_meps30.mean(), 1) if len(nc) >= MIN_EI else None,
        'nres_above_meps33_pct': round(100 * nc.above_meps33.mean(), 1) if len(nc) >= MIN_EI else None,
        'nres_ei_calc': _n(len(nc)),
        # Eko sklad: stanovanjske stavbe z vsaj enim podprtim ukrepom posamezne vrste (vsa leta do 2025)
        'es_res': {k: {'b': _n(int(res[f'es_{k}'].notna().sum())), 'pct': _pct(res[f'es_{k}'].notna().sum(), len(res), len(res), int(res[f'es_{k}'].notna().sum()))} for k in ES_SHOW},
        'es_res_any_pct': _pct((q := res[[f'es_{k}' for k in ES_GROUPS]].notna().any(axis=1).sum()), len(res), len(res), int(q)),
        # Kataster: vpisano leto obnove strehe, fasade ali oken
        'obnova_res_pct': _pct(res.obnova_any.sum(), len(res), len(res), int(res.obnova_any.sum())),
        'obnova_res_since2010_pct': _pct((q2 := (res[['obnova_streha', 'obnova_fasada', 'obnova_okna']] >= 2010).any(axis=1).sum()), len(res), len(res), int(q2)),
        # 10.5: javne stavbe po vrsti stavbe (agregat, brez seznama)
        'public_by_cat': {cid: ({'b': _n(int((m := g[(g.seg == 'javne') & (g.cat == cid)]).shape[0])), 'a': round(m.m2.sum() / 1e3, 1) if len(m) >= MIN_CELL else None})
                          for cid, *_ in CATS[2:]},
    }
    return out


def build(ctx: Context) -> dict:
    fond = json.loads((OUT / 'stavbni_fond.json').read_text(encoding='utf-8'))
    df = build_table(ctx)
    df['cls'] = _classify(df, fond)
    df = _flags(df, fond)

    # Kontrole proti osnutku: pokritost z izkaznicami (preglednica »Pokritost stavbnega fonda …«) in javne stavbe (preglednica 3).
    t6 = ctx.draft.table(r'Pokritost stavbnega fonda z veljavnimi energetskimi izkaznicami po segmentih')
    for seg, pat in [('hise', r'^Enodružinske'), ('bloki', r'^Večstanovanjske'), ('javne', r'^Javne'), ('zasebne', r'^Stavbe zasebnega')]:
        r = next(x for x in t6 if x and __import__('re').search(pat, x[0]))
        g = df[df.seg == seg]
        share = 100 * g.ei_any.mean()
        ref = float(r[4].replace(',', '.'))
        ctx.check(abs(share - ref) <= 1.0, f'občine: pokritost z izkaznicami {seg} {share:.1f} % ≈ osnutek {ref} % (±1 o. t.)')
    hg = df[(df.cat == 'HISA') & df.cls.notna()]
    g_share = 100 * (hg.cls == 'G').mean()
    ctx.check(10 <= g_share <= 20, f'občine: razred G pri hišah z izkaznico {g_share:.1f} % (definicija razreda G: najslabših 15 %, ±5 o. t.)')
    pub = int((df.seg == 'javne').sum())
    ctx.check(abs(pub - 11199) / 11199 <= 0.01, f'občine: javne stavbe po pretežni rabi {pub} ≈ osnutek 11.199 (±1 %)')
    ctx.check(int(df.seg.isin(['hise', 'bloki']).sum()) == 554471, 'občine: stanovanjske stavbe = 554.471 (preglednica pokritosti)')

    # Neskladje v osnutku, pomembno za kalibracijo modela po občinah (končna raba stanovanjskih stavb 2023).
    t14 = ctx.draft.table(r'Končna in primarna raba energije po segmentih stavb v izhodiščnih letih')
    t27 = ctx.draft.table(r'Končna raba energije v stavbah v opazovanih letih')
    from .draft import row
    from .numbers import num
    r14, r27 = num(row(t14, r'^Stanovanjske stavbe')[2]), num(row(t27, r'^Stanovanjski sektor skupaj')[2])
    ctx.warn_unless(abs(r14 - r27) < 1, f'končna raba stanovanjskih stavb 2023: izhodiščna preglednica {r14} ktoe ≠ preglednica »Končna raba energije v stavbah v opazovanih letih« {r27} ktoe')

    ob = json.loads(ctx.files['obcine'].read_text(encoding='utf-8'))
    zem = json.loads((OUT / 'zemljevid.json').read_text(encoding='utf-8'))
    muni = {str(f['properties']['EID_OBCINA']): (int(f['properties']['SIFRA']), f['properties']['NAZIV']) for f in ob['features']}
    ctx.check(set(df.obcina) <= set(muni), 'občine: vse stavbe imajo občino')

    si = _area(df)
    (OUT / 'obcine').mkdir(parents=True, exist_ok=True)
    index = []
    for eid, (sifra, name) in sorted(muni.items(), key=lambda x: x[1][1]):
        g = df[df.obcina == eid]
        a = _area(g)
        region = zem['municipalities'][eid]['region']
        write_json(f'obcine/{sifra}', {'meta': ctx.meta(_sources(), note=_NOTE), 'sifra': sifra, 'eid': eid, 'name': name,
                                       'region': region, 'region_name': zem['regions'][region]['name'], **a})
        rs = a['segments']
        index.append({'sifra': sifra, 'eid': eid, 'name': name, 'region': region, 'buildings': a['buildings'], 'area_k_m2': a['area_k_m2'],
                      'ei_area_res_pct': _pct(g[g.seg.isin(['hise', 'bloki']) & g.ei_any].m2.sum(), g[g.seg.isin(['hise', 'bloki'])].m2.sum(), 99, int((g.seg.isin(['hise', 'bloki']) & g.ei_any).sum())),
                      'hise_ei_pct': rs['hise']['ei_buildings_pct'], 'res_above43_pct': a['res_above43_pct'],
                      'es_res_any_pct': a['es_res_any_pct'], 'obnova_res_pct': a['obnova_res_pct'],
                      'pre1981_res_area_pct': _pct(g[g.seg.isin(['hise', 'bloki']) & (g.year < 1981)].m2.sum(), g[g.seg.isin(['hise', 'bloki'])].m2.sum(), 99, int((g.seg.isin(['hise', 'bloki']) & (g.year < 1981)).sum()))})
    ctx.check(len(index) == 212, 'občine: 212 občin')
    ctx.check(sum(x['buildings'] for x in index) == len(df), 'občine: vsota stavb po občinah = vse stavbe')

    res_all = df[df.seg.isin(['hise', 'bloki'])]
    data = {
        'meta': ctx.meta(_sources(), note=_NOTE),
        'min_cell': MIN_CELL, 'min_ei': MIN_EI, 'classes': CLS, 'class_groups': list(GROUPS), 'periods': PERIODS,
        'segments': [{'id': s, 'name': n} for s, n in SEGS],
        'es_groups': [{'id': k, 'name': ES_NAMES[k]} for k in ES_SHOW],
        'categories': [{'id': c[0], 'name': c[1]} for c in CATS],
        'si': {**si, 'ei_area_res_pct': round(100 * res_all[res_all.ei_any].m2.sum() / res_all.m2.sum(), 1),
               'pre1981_res_area_pct': round(100 * res_all[res_all.year < 1981].m2.sum() / res_all.m2.sum(), 1)},
        'municipalities': index,
    }
    write_json('obcine_index', data)
    _mini_map(ob)
    write_csv('obcine', ['občina', 'šifra', 'stavbe', 'površina [tisoč m²]', 'stanovanjska površina z izkaznico [%]', 'hiše z izkaznico [%]',
                         'stanovanjske stavbe z izkaznico nad pragom 43 % [%]', 'stanovanjske stavbe z ukrepom Eko sklada [%]',
                         'stanovanjske stavbe z vpisano obnovo v katastru [%]', 'stanovanjska površina pred 1981 [%]'],
              [[x['name'], x['sifra'], x['buildings'], x['area_k_m2'], x['ei_area_res_pct'], x['hise_ei_pct'], x['res_above43_pct'],
                x['es_res_any_pct'], x['obnova_res_pct'], x['pre1981_res_area_pct']] for x in index])
    return data


def _sources():
    return ['Kataster nepremičnin GURS, stavbe in deli stavb, 30. 8. 2026 (razvrstitev v kategorije EPBD kot v osnutku NPS 2050)',
            'Register energetskih izkaznic, veljavne izkaznice na dan 28. 9. 2026',
            'Eko sklad: podprte naložbe po stavbah do leta 2025',
            'Meje energijskih razredov, prag 43 % in pragovi minimalnih standardov: osnutek NPS 2050']


_NOTE = ('Samo agregati. Deleži med stavbami z izkaznico so prikazani pri vsakem številu izkaznic, skupaj s številom izkaznic. Razredi A–G so določeni iz primarne energije '
         'računskih izkaznic po mejah NPS 2050 za kategorijo stavbe; deleži nad pragovi veljajo za stavbe z izkaznico (vzorec). '
         'Javne stavbe po pretežni dejanski rabi delov stavbe (brez pomožnih prostorov). Eko sklad: stavbe z vsaj enim podprtim ukrepom.')


def _mini_map(ob: dict, tol: float = 0.005, width: int = 1000):
    """Poenostavljene meje občin kot poti SVG (za naslovno stran), v preprosti projekciji (dolžina × cos 46°)."""
    import math
    from shapely.geometry import shape
    k = math.cos(math.radians(46.1))
    geoms = [(int(f['properties']['SIFRA']), shape(f['geometry']).simplify(tol, preserve_topology=True)) for f in ob['features']]
    minx = min(g.bounds[0] for _, g in geoms) * k; maxx = max(g.bounds[2] for _, g in geoms) * k
    miny = min(g.bounds[1] for _, g in geoms); maxy = max(g.bounds[3] for _, g in geoms)
    sc = width / (maxx - minx)
    ring = lambda c: 'M' + 'L'.join(f'{(x * k - minx) * sc:.0f},{(maxy - y) * sc:.0f}' for x, y in c) + 'Z'
    paths = {}
    for sifra, g in geoms:
        polys = [g] if g.geom_type == 'Polygon' else list(g.geoms)
        paths[str(sifra)] = ''.join(ring(p.exterior.coords) for p in polys)
    (OUT / 'obcine_mini.json').write_text(json.dumps({'w': width, 'h': round((maxy - miny) * sc), 'paths': paths}, separators=(',', ':')), encoding='utf-8')
