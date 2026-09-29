"""Zemljevid stavbnega fonda po statističnih regijah in občinah.

Viri: kataster nepremičnin (stavbe, razvrščene v kategorije EPBD) in meje GURS (Register prostorskih enot).
Objavijo se samo seštevki; celice z manj kot 5 stavbami se ne objavijo. Stavbe brez leta gradnje (74) so izpuščene,
tako se seštevki ujemajo s preglednicami v osnutku (597.365 stavb).
"""
import json

import pandas as pd
import topojson
from shapely.geometry import shape

from .context import OUT, Context, write_csv, write_json
from .stavbni_fond import CATS, MIN_CELL

CAT_NAME = {c[0]: c[1] for c in CATS}
CAT_SEG = {c[0]: c[2] for c in CATS}
PRE = 1981  # stavbe, zgrajene pred prvimi toplotnimi predpisi (pogl. 2.2.5.2)
SIMPLIFY = 0.0008  # stopinje (~60–90 m); topologija se ohrani, sosednje občine ostanejo stikajoče


def _suppress(n: int):
    return 0 < n < MIN_CELL


def _geo(fc: dict, key: str, name: str, extra=lambda p: {}) -> dict:
    """Poenostavitev z ohranjanjem topologije in zaokrožitev koordinat na 4 decimalke (~10 m)."""
    src = {'type': 'FeatureCollection', 'features': [
        {'type': 'Feature', 'geometry': f['geometry'],
         'properties': {'id': str(f['properties'][key]), 'name': f['properties'][name], **extra(f['properties'])}}
        for f in fc['features']]}
    simp = json.loads(topojson.Topology(src, prequantize=1e6, toposimplify=SIMPLIFY).to_geojson())

    def rnd(c):
        return [round(c[0], 4), round(c[1], 4)] if isinstance(c[0], (int, float)) else [rnd(x) for x in c]

    for f in simp['features']:
        f['geometry']['coordinates'] = rnd(f['geometry']['coordinates'])
        f.pop('id', None)
    return simp


def build(ctx: Context) -> dict:
    df = pd.read_csv(ctx.files['kataster_stavbe'], usecols=['EID_OBCINA', 'EPBD', 'UPORABNA_POVRSINA_EPBD', 'LETO_IZGRA'],
                     dtype={'EID_OBCINA': str})
    df['EID_OBCINA'] = df['EID_OBCINA'].str.replace(r'\.0$', '', regex=True)
    no_year = int(df['LETO_IZGRA'].isna().sum())
    df = df[df['LETO_IZGRA'].notna()].copy()
    df['pre'] = df['LETO_IZGRA'] < PRE
    df['m2'] = df['UPORABNA_POVRSINA_EPBD']

    ob = json.loads(ctx.files['obcine'].read_text(encoding='utf-8'))
    rg = json.loads(ctx.files['regije'].read_text(encoding='utf-8'))
    ctx.check(len(ob['features']) == 212 and len(rg['features']) == 12, 'meje: 212 občin in 12 statističnih regij')

    # Občina → regija po legi (točka znotraj občine, ki zagotovo leži v njej).
    regions = [(str(f['properties']['SIFRA']), f['properties']['NAZIV'], shape(f['geometry'])) for f in rg['features']]
    muni = {}
    for f in ob['features']:
        p = f['properties']
        pt = shape(f['geometry']).representative_point()
        hits = [r for r in regions if r[2].contains(pt)]
        ctx.check(len(hits) == 1, f'občina {p["NAZIV"]} leži v natanko eni regiji')
        muni[str(p['EID_OBCINA'])] = {'name': p['NAZIV'], 'region': hits[0][0]}
    ctx.check(set(df['EID_OBCINA']) <= set(muni), 'vse stavbe v katastru imajo občino z mejo v RPE')

    df['region'] = df['EID_OBCINA'].map(lambda e: muni[e]['region'])

    # Kontrola s preglednico v osnutku (prek stavbni_fond.json iz istega cevovoda).
    fond = json.loads((OUT / 'stavbni_fond.json').read_text(encoding='utf-8'))
    for c in fond['categories']:
        n = int((df['EPBD'] == c['id']).sum())
        ctx.check(n == c['buildings'], f'zemljevid: {c["id"]} {n} stavb = osnutek ({c["buildings"]})')
    ctx.check(len(df) == fond['segments']['skupaj']['buildings'],
              f'zemljevid: {len(df)} stavb (brez {no_year} brez leta gradnje) = osnutek')

    def agg(g: pd.DataFrame) -> dict:
        res = g['EPBD'].map(CAT_SEG) == 'stanovanjske'
        cats = {}
        for cid in CAT_NAME:
            s = g[g['EPBD'] == cid]
            n = len(s)
            cats[cid] = None if _suppress(n) else {'b': n, 'a': round(s['m2'].sum() / 1e3, 1)}  # a = tisoč m²
        area = g['m2'].sum()
        return {
            'buildings': len(g),
            'area_k_m2': round(area / 1e3, 1),
            'res_area_k_m2': round(g.loc[res, 'm2'].sum() / 1e3, 1),
            'nonres_area_k_m2': round(g.loc[~res, 'm2'].sum() / 1e3, 1),
            'pre1981_area_pct': round(100 * g.loc[g['pre'], 'm2'].sum() / area, 1) if area else None,
            'cats': cats,
        }

    regions_out = {}
    for code, name, _ in regions:
        g = df[df['region'] == code]
        regions_out[code] = {'name': name, **agg(g)}
    munis_out = {}
    for eid, m in muni.items():
        g = df[df['EID_OBCINA'] == eid]
        munis_out[eid] = {'name': m['name'], 'region': m['region'], **agg(g)}
    ctx.check(sum(r['buildings'] for r in regions_out.values()) == len(df), 'vsota regij = vse stavbe')
    ctx.check(sum(m['buildings'] for m in munis_out.values()) == len(df), 'vsota občin = vse stavbe')
    suppressed = sum(1 for m in munis_out.values() for v in m['cats'].values() if v is None)

    geo_ob = _geo(ob, 'EID_OBCINA', 'NAZIV')
    geo_rg = _geo(rg, 'SIFRA', 'NAZIV')
    for fname, g in [('zemljevid_obcine.geojson', geo_ob), ('zemljevid_regije.geojson', geo_rg)]:
        (OUT / fname).write_text(json.dumps(g, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    ctx.check((OUT / 'zemljevid_obcine.geojson').stat().st_size < 900_000, 'poenostavljene meje občin < 900 KB')

    data = {
        'meta': ctx.meta(
            ['Kataster nepremičnin GURS (stavbe, razvrščene v kategorije EPBD, 2026)',
             'Meje občin in statističnih regij: GURS, Register prostorskih enot (CC BY 4.0), poenostavljene'],
            note=f'Seštevki po občinah in regijah. Izpuščenih je {no_year} stavb brez leta gradnje, zato se seštevki ujemajo '
                 f'z osnutkom NPS 2050. '
                 f'Površina v tisoč m² uporabne površine; delež pred {PRE} = delež uporabne površine stavb, zgrajenih pred letom {PRE}.'),
        'categories': [{'id': c, 'name': n, 'segment': CAT_SEG[c]} for c, n in CAT_NAME.items()],
        'regions': regions_out,
        'municipalities': munis_out,
    }
    write_json('zemljevid', data)
    head = ['ime', 'stavbe', 'površina [tisoč m²]', 'stanovanjska površina [tisoč m²]', 'nestanovanjska površina [tisoč m²]',
            f'delež površine pred {PRE} [%]'] + [f'{n}: stavbe' for n in CAT_NAME.values()]
    row = lambda r: [r['name'], r['buildings'], r['area_k_m2'], r['res_area_k_m2'], r['nonres_area_k_m2'], r['pre1981_area_pct']] + \
        [(r['cats'][c] or {}).get('b') for c in CAT_NAME]
    write_csv('zemljevid_regije', ['regija'] + head[1:], [row(r) for r in regions_out.values()])
    write_csv('zemljevid_obcine', ['občina', 'regija'] + head[1:],
              [[m['name'], regions_out[m['region']]['name']] + row(m)[1:] for m in sorted(munis_out.values(), key=lambda x: x['name'])])
    return data
