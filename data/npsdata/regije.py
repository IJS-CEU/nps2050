"""Energetsko-podnebne kartice 12 statističnih regij (za regionalne energetske agencije): seštevki občinskih podatkov.

Seštevki: prebivalci, raba energije, emisije, obseg prenove, naložbe, spodbude, število stavb za prenovo.
Deleži in kazalniki na m² ali prebivalca so ponovno izračunani iz seštevkov (tehtano z rabo energije ali stanovanjsko površino).
Semafor tempa prenove: enaka metoda B kot pri občinah (stopnja iz registrov 2023–2025, tehtana s stanovanjsko površino).
"""
import json

from .context import OUT, Context, write_csv, write_json

MIN_REN = 10


def _load(name):
    return json.loads((OUT / f'{name}.json').read_text(encoding='utf-8'))


def build(ctx: Context) -> dict:
    md, ix, zm = _load('obcine_model'), _load('obcine_index'), _load('zemljevid')
    ms = md['si']
    rows = {str(r['sifra']): r for r in ix['municipalities']}
    res_area = {str(r['sifra']): zm['municipalities'][r['eid']]['res_area_k_m2'] * 1000 for r in ix['municipalities']}
    regs = {rid: [s for s, r in rows.items() if r['region'] == rid] for rid in zm['regions']}
    ctx.check(sum(len(v) for v in regs.values()) == 212 and len(regs) == 12, 'regije: 212 občin v 12 regijah')

    st_si = ms['stevilke']
    act_si, req_si = st_si['stopnja_dejanska_pct'], st_si['stopnja_zahtevana_pct']
    out, csv_rows = {}, []
    for rid, ss in regs.items():
        M = [md['municipalities'][s] for s in ss]
        sm = lambda f: sum(f(m) for m in M)
        wavg = lambda f, w: sum(f(m) * w(m) for m in M) / sm(w) if sm(w) else None
        rnd = lambda v, n=1: None if v is None else round(v, n)
        pop = sm(lambda m: m['vse']['pop'])
        fe = {k: sm(lambda m: m['vse']['fe_gwh'][k]) for k in ('res', 'nres', 'total')}
        tgp = {k: sm(lambda m: m['vse']['tgp_kt'][k]) for k in ('res', 'nres', 'total')}
        ra = sum(res_area[s] for s in ss)
        ove = {k: rnd(wavg(lambda m: m['vse']['ove_pct'][k], lambda m: m['vse']['fe_gwh'][k])) for k in ('res', 'nres', 'total')}
        pot = {}
        for y in ('2023', '2030', '2040', '2050'):
            f = sm(lambda m: m['pot'][y]['fe_gwh'])
            pot[y] = {'fe_gwh': rnd(f), 'tgp_kt': rnd(sm(lambda m: m['pot'][y]['tgp_kt']), 2),
                      'ove_pct': rnd(sum(m['pot'][y]['ove_pct'] * m['pot'][y]['fe_gwh'] for m in M) / f),
                      'fossil_pct': rnd(sum((m['pot'][y]['fossil_pct'] or 0) * m['pot'][y]['fe_gwh'] for m in M) / f)}
        ci = [m['cilji'] for m in M]
        st = [m['stevilke'] for m in M]
        n_ren = sum(x['prenov_registri'] for x in st)
        act = sum((x['stopnja_dejanska_pct'] or 0) * res_area[s] for x, s in zip(st, ss)) / ra
        req = sum((x['stopnja_zahtevana_pct'] or 0) * res_area[s] for x, s in zip(st, ss)) / ra
        sem = 'ni podatka' if n_ren < MIN_REN else ('na poti' if act / act_si >= req / req_si else 'pod ciljem')
        dh_fe, dh_dense = sm(lambda m: m['dh_pot']['fe_gwh']), sm(lambda m: m['dh_pot']['fe_dense_gwh'])
        r = {
            'id': rid, 'name': zm['regions'][rid]['name'], 'n_obcin': len(ss),
            'buildings': zm['regions'][rid]['buildings'], 'area_k_m2': zm['regions'][rid]['area_k_m2'], 'res_area_k_m2': round(ra / 1000, 1),
            'pre1981_area_pct': zm['regions'][rid]['pre1981_area_pct'],
            'vse': {'pop': pop, 'fe_gwh': {k: rnd(v) for k, v in fe.items()}, 'tgp_kt': {k: rnd(v, 2) for k, v in tgp.items()}, 'ove_pct': ove,
                    'fe_mwh_preb': {'res': rnd(1000 * fe['res'] / pop, 2), 'total': rnd(1000 * fe['total'] / pop, 2)},
                    'tgp_t_preb': {'res': rnd(1000 * tgp['res'] / pop, 2), 'total': rnd(1000 * tgp['total'] / pop, 2)}},
            'fe_kwh_m2': round(1e6 * fe['res'] / ra),
            'carriers_pct': {c['id']: rnd(wavg(lambda m, c=c: m['carriers_pct'][c['id']], lambda m: m['fe_gwh'])) for c in md['carriers']},
            'nps_pct': {k: rnd(sum(m['nps_pct'][k] * res_area[s] for m, s in zip(M, ss)) / ra) for k in md['classes']},
            'above43_area_pct': rnd(sum(m['above43_area_pct'] * res_area[s] for m, s in zip(M, ss)) / ra),
            'dh_pot': {'fe_gwh': rnd(dh_fe), 'fe_pct': rnd(100 * dh_dense / dh_fe), 'fe_ha': sm(lambda m: m['dh_pot']['fe_ha'])},
            'pot': pot,
            'cilji': {'prenova_m2_leto': {k: round(sum(c['prenova_skupaj_m2_leto'][k] for c in ci), -2) for k in ('2026_2030', '2031_2040')},
                      'wpb_m2_leto': round(sum(c['wpb']['m2_leto_2026_2030'] for c in ci), -2),
                      'meps_n_2030': sum(c['meps']['n_2030'] for c in ci),
                      'elko_gwh': [rnd(sum(c['fosilna']['elko']['gwh_2023'] for c in ci))] + [rnd(sum(c['fosilna']['elko']['gwh'][i] for c in ci)) for i in range(3)],
                      'plin_gwh': [rnd(sum(c['fosilna']['gas']['gwh_2023'] for c in ci))] + [rnd(sum(c['fosilna']['gas']['gwh'][i] for c in ci)) for i in range(3)]},
            'stevilke': {'hise_leto': sum(x['hise_leto'] or 0 for x in st), 'stanovanja_leto': sum(x['stanovanja_leto'] or 0 for x in st),
                         'javne_leto': sum(x['javne_leto'] or 0 for x in st), 'zasebne_leto': sum(x['zasebne_leto'] or 0 for x in st),
                         'nalozba_eur_leto': round(sum(x['nalozba_eur_leto'] for x in st), -5), 'spodbude_eur_leto': round(sum(x['spodbude_eur_leto'] for x in st), -5),
                         'semafor': sem, 'stopnja_dejanska_pct': round(act, 2), 'stopnja_zahtevana_pct': round(req, 2), 'prenov_registri': n_ren,
                         'obcine_semafor': {k: sum(1 for x in st if x['semafor'] == k) for k in ('na poti', 'pod ciljem', 'ni podatka')}},
            'obcine': sorted([{'sifra': int(s), 'name': m['name'], 'pop': m['vse']['pop'], 'fe_mwh_preb': m['vse']['fe_mwh_preb']['total'],
                               'tgp_t_preb': m['vse']['tgp_t_preb']['total'], 'ove_pct': m['vse']['ove_pct']['total'],
                               'above43_area_pct': m['above43_area_pct'], 'semafor': m['stevilke']['semafor']} for m, s in zip(M, ss)],
                             key=lambda o: o['name']),
        }
        out[rid] = r
        csv_rows.append([r['name'], r['n_obcin'], pop, r['buildings'], r['area_k_m2'], fe['total'], fe['res'], tgp['total'], ove['total'],
                         r['vse']['fe_mwh_preb']['total'], r['above43_area_pct'], r['cilji']['prenova_m2_leto']['2026_2030'],
                         r['stevilke']['nalozba_eur_leto'], r['stevilke']['stopnja_dejanska_pct'], r['stevilke']['stopnja_zahtevana_pct'], sem])

    ctx.check(abs(sum(r['vse']['pop'] for r in out.values()) - ms['vse']['pop']) <= 5, 'regije: vsota prebivalcev = Slovenija')
    ctx.check(abs(sum(r['vse']['fe_gwh']['total'] for r in out.values()) / ms['vse']['fe_gwh']['total'] - 1) < 0.005, 'regije: vsota rabe končne energije = Slovenija (±0,5 %)')
    ctx.check(sum(r['buildings'] for r in out.values()) == sum(z['buildings'] for z in zm['regions'].values()), 'regije: vsota stavb')
    data = {'meta': ctx.meta(['Seštevki občinskih podatkov (obcine_model.json, obcine_index.json, zemljevid.json)'],
                             note='Seštevki občin po statističnih regijah; deleži tehtani z rabo energije ali stanovanjsko površino. Cilji so državni cilji NPS 2050, preneseni sorazmerno s stavbnim fondom.'),
            'regions': out}
    write_json('regije', data)
    write_csv('regije', ['regija', 'občin', 'prebivalci', 'stavbe', 'površina (tisoč m²)', 'raba končne energije (GWh)', 'od tega stanovanjske (GWh)',
                         'emisije TGP (kt CO2 ekv.)', 'delež OVE (%)', 'raba končne energije na prebivalca (MWh)', 'stanovanjska površina med 43 % najmanj učinkovitih (%)',
                         'potrebna prenova 2026–2030 (m²/leto)', 'naložbe (€/leto)', 'stopnja prenove 2023–2025 (%/leto)', 'zahtevana stopnja (%/leto)', 'tempo prenove'], csv_rows)
    return data
