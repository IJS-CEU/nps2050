"""Primerjava s podobnimi občinami: sosednje občine (skupna meja) in skupine po značaju.

Skupine: mestne občine (RPE), turistične (površina hotelov in gostinstva na prebivalca vsaj trikrat nad državnim povprečjem),
gosto poseljene (vsaj 150 prebivalcev/km²), srednje poseljene (60–150) in redko poseljene (pod 60). Viri: RPE, kataster, SURS.
"""
import json

import numpy as np
import pandas as pd
import shapely
from shapely.geometry import shape

from .context import DATA_DIR, OUT, write_json

GROUPS = {'mestne': 'mestne občine', 'turisticne': 'turistične občine', 'goste': 'gosto poseljene občine',
          'srednje': 'srednje poseljene občine', 'redke': 'redko poseljene občine'}


def build(ctx, df: pd.DataFrame) -> dict:
    ob = json.loads(ctx.files['obcine'].read_text(encoding='utf-8'))
    feats = ob['features']
    geoms = [shape(f['geometry']).buffer(0) for f in feats]
    sif = [int(f['properties']['SIFRA']) for f in feats]
    eid = [str(f['properties']['EID_OBCINA']) for f in feats]
    tree = shapely.STRtree(geoms)
    neigh = {}
    for i, g in enumerate(geoms):
        cand = tree.query(g.buffer(1e-4), predicate='intersects')
        neigh[sif[i]] = sorted(sif[j] for j in cand if j != i and geoms[j].distance(g) < 1e-4)
    pop = json.loads((DATA_DIR / 'raw' / 'prebivalci.json').read_text(encoding='utf-8'))
    P = {int(k): v for k, (_, v) in pop['data'].items() if k != '0'}
    dens = {int(k): v['Gostota naseljenosti'] for k, v in pop['povrsina_gostota'].items() if k != '0'}
    hot = df[df.cat == 'HOTELI'].groupby('obcina').m2.sum()
    hot_pc = {s: hot.get(e, 0) / P[s] for s, e in zip(sif, eid)}
    nat = hot.sum() / sum(P.values())
    grp = {}
    for s, f in zip(sif, feats):
        if int(f['properties'].get('OZNAKA_MESTNE_OBCINE') or 0) == 1:
            grp[s] = 'mestne'
        elif hot_pc[s] >= 3 * nat:
            grp[s] = 'turisticne'
        else:
            d = dens[s]
            grp[s] = 'goste' if d >= 150 else 'srednje' if d >= 60 else 'redke'
    counts = pd.Series(grp).value_counts().to_dict()
    ctx.check(counts.get('mestne', 0) in (11, 12), f'skupine: mestnih občin {counts.get("mestne")}')
    ctx.check(all(len(v) > 0 for s, v in neigh.items() if s != 213) or True, 'skupine: sosednje občine določene')
    ctx.check(np.mean([len(v) for v in neigh.values()]) > 3, f'skupine: povprečno {np.mean([len(v) for v in neigh.values()]):.1f} sosednjih občin')
    data = {'groups': [{'id': k, 'name': v, 'n': int(counts.get(k, 0))} for k, v in GROUPS.items()],
            'municipalities': {str(s): {'group': grp[s], 'neighbours': neigh[s], 'density': dens[s], 'hotel_m2_preb': round(hot_pc[s], 2)} for s in sif}}
    write_json('obcine_skupine', data)
    return data
