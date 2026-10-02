"""11.7 »Kaj pomeni cilj za občino« v številkah (potrdil Gašper 2. 10. 2026; semafor različica B).

- Pretvorba letnega obsega prenove (m²) v število hiš, stanovanj ter javnih in storitvenih stavb s povprečnimi površinami v občini (kataster).
- Potrebna naložba = obseg × specifični strošek po segmentih, delež nepovratnih spodbud po segmentih (osnutek, preglednica 54; državno povprečje).
- Semafor (relativni): stopnja prenove stanovanjskih stavb iz registrov 2023–2025 (vpisana obnova fasade, strehe ali oken v katastru ali ukrep
  Eko sklada za ovoj ali okna), deljena s slovensko; »na poti«, če ni manjša od razmerja zahtevane stopnje občine in Slovenije.
  »Ni podatka« pri manj kot 10 prenovljenih stanovanjskih stavbah v treh letih.
- Rang med 212 občinami in v skupini za tri kazalnike.
"""
import json

import pandas as pd

from .context import OUT, write_json
from .draft import row
from .numbers import num

MIN_REN = 10
SEG_RES = {'hise': 'res', 'bloki': 'res', 'javne': 'javne', 'zasebne': 'zasebne'}
RANG = [('pre1981_res_area_pct', 'stanovanjska površina, zgrajena pred 1981', 'nizko'),
        ('w_res_model_pct', 'stanovanjska površina v skupini 43 % najmanj učinkovitih', 'nizko'),
        ('ei_area_res_pct', 'pokritost stanovanjske površine z energetskimi izkaznicami', 'visoko')]


def build(ctx, df: pd.DataFrame, out: dict, muni: dict, si_out: dict) -> dict:
    t54 = ctx.draft.table(r'Vhodni parametri ocene investicijskih potreb')
    k = {'res': row(t54, r'^Stanovanjske stavbe'), 'javne': row(t54, r'^Javne stavbe'), 'zasebne': row(t54, r'^Zasebne storitvene')}
    eur = {s: num(r[3]) for s, r in k.items()}
    grant = {s: num(r[5]) / 100 for s, r in k.items()}
    nat_vol = num(row(t54, r'^Skupaj')[1]) * 1000  # m² na leto 2026–2030
    ctx.check(300 < eur['res'] < 400 and 0.05 < grant['res'] < 0.3, f'konstante 11.7: {eur}, {grant}')

    # povprečne površine po občinah (kataster)
    b = df.copy()
    av = {'hise': b[b.seg == 'hise'].groupby('obcina').m2.mean(),
          'bloki': b[b.seg == 'bloki'].groupby('obcina').m2.sum() / b[b.seg == 'bloki'].groupby('obcina').n_stan.sum(),
          'javne': b[b.seg == 'javne'].groupby('obcina').m2.mean(),
          'zasebne': b[b.seg == 'zasebne'].groupby('obcina').m2.mean()}
    av_si = {'hise': b[b.seg == 'hise'].m2.mean(), 'bloki': b[b.seg == 'bloki'].m2.sum() / b[b.seg == 'bloki'].n_stan.sum(),
             'javne': b[b.seg == 'javne'].m2.mean(), 'zasebne': b[b.seg == 'zasebne'].m2.mean()}

    # dejanska stopnja prenove stanovanjskih stavb iz registrov 2023–2025 (delež površine na leto)
    r = b[b.seg.isin(['hise', 'bloki'])].copy()
    y = lambda c: pd.to_numeric(r[c], errors='coerce')
    ren = y('obnova_fasada').between(2023, 2025) | y('obnova_streha').between(2023, 2025) | y('obnova_okna').between(2023, 2025) \
        | r.es_ovoj.between(2023, 2025) | r.es_okna.between(2023, 2025)
    r['ren'] = ren
    g = r.groupby('obcina')
    act = g.apply(lambda x: x.m2[x.ren].sum() / x.m2.sum() / 3)
    n_ren = g.ren.sum()
    act_si = r.m2[r.ren].sum() / r.m2.sum() / 3
    res_area = g.m2.sum()

    ix = json.loads((OUT / 'obcine_index.json').read_text(encoding='utf-8'))
    sk = json.loads((OUT / 'obcine_skupine.json').read_text(encoding='utf-8'))
    rows = {str(x['sifra']): x for x in ix['municipalities']}
    for s in rows:  # kazalnik 11.8 je v modelu (worst), v kazalu še ni zapisan
        rows[s]['w_res_model_pct'] = out[s]['worst']['res_model_pct']

    def rank(key, s, pool, smer):
        vals = [(x[key], str(x['sifra'])) for x in pool if x.get(key) is not None]
        vals.sort(key=lambda t: t[0], reverse=(smer == 'visoko'))
        pos = next((i + 1 for i, (_, ss) in enumerate(vals) if ss == s), None)
        return {'mesto': pos, 'od': len(vals)}

    req_si_num = sum(o['cilji']['prenova_m2_leto']['hise']['2026_2030'] + o['cilji']['prenova_m2_leto']['bloki']['2026_2030'] for o in out.values())
    req_si = req_si_num / r.m2.sum()
    tot_vol = 0.0
    for eid, (s, _) in muni.items():
        s = str(s)
        o = out[s]
        pm = o['cilji']['prenova_m2_leto']
        cnt = {seg: round(pm[seg]['2026_2030'] / (av[seg].get(eid) or av_si[seg])) if (av[seg].get(eid) or av_si[seg]) else None for seg in pm}
        inv = {seg: pm[seg]['2026_2030'] * eur[SEG_RES[seg]] for seg in pm}
        sub = {seg: inv[seg] * grant[SEG_RES[seg]] for seg in pm}
        tot_vol += sum(pm[seg]['2026_2030'] for seg in pm)
        req = (pm['hise']['2026_2030'] + pm['bloki']['2026_2030']) / res_area.get(eid, float('nan'))
        a = act.get(eid)
        if n_ren.get(eid, 0) < MIN_REN or a is None or pd.isna(req):
            sem = 'ni podatka'
        else:
            sem = 'na poti' if (a / act_si) >= (req / req_si) else 'pod ciljem'
        grp = sk['municipalities'][s]['group']
        pool_g = [x for x in rows.values() if sk['municipalities'][str(x['sifra'])]['group'] == grp]
        o['stevilke'] = {
            'hise_leto': cnt['hise'], 'stanovanja_leto': cnt['bloki'], 'javne_leto': cnt['javne'], 'zasebne_leto': cnt['zasebne'],
            'povrsina_hise': round(av['hise'].get(eid, av_si['hise'])), 'povrsina_stanovanja': round(av['bloki'].get(eid, av_si['bloki'])),
            'nalozba_eur_leto': round(sum(inv.values()), -4), 'nalozba_eur_2030': round(5 * sum(inv.values()), -5),
            'spodbude_eur_leto': round(sum(sub.values()), -4), 'spodbude_delez_pct': round(100 * sum(sub.values()) / sum(inv.values())) if sum(inv.values()) else None,
            'semafor': sem, 'stopnja_dejanska_pct': round(100 * a, 2) if a is not None and not pd.isna(a) else None,
            'stopnja_zahtevana_pct': round(100 * req, 2) if not pd.isna(req) else None, 'prenov_registri': int(n_ren.get(eid, 0)),
            'indeks_tempo': round((a / act_si) / (req / req_si), 2) if sem != 'ni podatka' else None,
            'rang': {key: {'vse': rank(key, s, list(rows.values()), smer), 'skupina': rank(key, s, pool_g, smer), 'oznaka': lab, 'smer': smer}
                     for key, lab, smer in RANG},
        }
    ctx.check(abs(tot_vol / nat_vol - 1) < 0.01, f'11.7: vsota občinskih ciljev {tot_vol / 1e3:.1f} tisoč m²/leto = državni obseg {nat_vol / 1e3:.1f} (±1 %)')
    sems = pd.Series([o['stevilke']['semafor'] for o in out.values()]).value_counts().to_dict()
    ctx.check(sems.get('na poti', 0) > 20 and sems.get('pod ciljem', 0) > 20, f'11.7: semafor {sems}')
    si_out['stevilke'] = {'stopnja_dejanska_pct': round(100 * act_si, 2), 'stopnja_zahtevana_pct': round(100 * req_si, 2),
                          'povrsina_hise': round(av_si['hise']), 'povrsina_stanovanja': round(av_si['bloki']), 'semafor': sems}
    konst = {'meta': ctx.meta([f'{ctx.draft.name}: preglednica 54 »Vhodni parametri ocene investicijskih potreb« (pogl. 7)',
                               'Kataster nepremičnin GURS (povprečne površine), Eko sklad (ukrepi 2023–2025)'],
                              note='Konstante za pretvorbe na straneh občin (11.7). Spodbude so državno povprečje.'),
             'strosek_eur_m2': eur, 'delez_spodbud': grant, 'drzavni_obseg_m2_leto': nat_vol, 'semafor': {'metoda': 'B (relativna)', 'min_prenov': MIN_REN}}
    write_json('konstante', konst)
    return konst
