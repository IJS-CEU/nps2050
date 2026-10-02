"""11.4 Tipični paketi prenove s stroški: delna, celovita (do razreda A po primarni energiji) in celovita ZEB prenova.

Viri (potrdil Gašper 2. 10. 2026):
- stroški: Eko sklad 2023–2025, priznani stroški na m² ogrevane uporabne površine po GURS (analiza Stroski_EUR_m2);
  delna in celovita prenova iz dejanskih kombinacij ukrepov pri isti stavbi, celovita ZEB iz ukrepa »celovita obnova
  stanovanjske stavbe« in »sNES+ prenova« 2024–2025;
- raba končne energije po razredih toplotnih potreb: osnutek, preglednica 23 (model RenRates);
- primarna energija pred prenovo: mediana neprenovljenih stavb z računsko izkaznico;
- cene energentov za gospodinjstva: SURS (tabela H028S, povprečje četrtletij 2025); daljinska toplota: Agencija za energijo,
  Analiza cen toplote 2025 (povprečje sistemov GJS za značilnega odjemalca v večstanovanjski stavbi, s prispevki in DDV);
- spodbude: predlog ukrepa N1 (osnutek, preglednica 26).
"""
import json
import urllib.request

import numpy as np
import pandas as pd

from .context import DATA_DIR, Context, write_json

CACHE = DATA_DIR / 'raw' / 'surs_cene_2025.json'
KWH_PER_L_OLJE = 10.0           # kurilna vrednost ekstra lahkega kurilnega olja, kWh/l
DH_EUR_KWH = 0.16998            # Agencija za energijo, Analiza cen toplote 2025: GJS, 69 m² stanovanje, s prispevki in DDV
DH_VIR = 'Agencija za energijo, Analiza cen toplote iz distribucijskih sistemov za leto 2025 (povprečje GJS, značilni odjemalec v večstanovanjski stavbi, s prispevki in DDV)'
# stanje po celoviti prenovi
Q_B1, ETA, DHW, SCOP, AUX = 20.0, 0.9, 15.0, 3.5, 3.0
FP = {'el': 2.5, 'amb': 1.0, 'olje': 1.1, 'dh': 1.23}    # faktorji skupne primarne energije (zakonski 2025, kot v osnutku)
PV_SHARE = 0.4                                            # ZEB: delež letne rabe elektrike, pokrit s sončno elektrarno na stavbi
GRP = {'do 1945': 'do1980', '1946–1970': 'do1980', '1971–1980': 'do1980', '1981–1990': '1981_2002', '1991–2002': '1981_2002'}
TYPES = [
    ('hisa_do1980', 'Enodružinska hiša, zgrajena do leta 1980', 'SFH', 'do1980', 'kurilno olje'),
    ('hisa_1981_2002', 'Enodružinska hiša, zgrajena 1981–2002', 'SFH', '1981_2002', 'kurilno olje'),
    ('blok_do1980', 'Stanovanje v bloku, zgrajenem do leta 1980', 'MFH', 'do1980', 'daljinsko ogrevanje'),
    ('blok_1981_2002', 'Stanovanje v bloku, zgrajenem 1981–2002', 'MFH', '1981_2002', 'daljinsko ogrevanje'),
]
UKREPI = {
    ('SFH', 'delna'): ['izolacija fasade', 'zamenjava oken'],
    ('SFH', 'celovita'): ['izolacija fasade in strehe', 'zamenjava oken', 'toplotna črpalka', 'prezračevanje z vračanjem toplote'],
    ('SFH', 'zeb'): ['vse iz celovite prenove', 'izolacija tal', 'sončna elektrarna', 'zahteve brezemisijske stavbe (sNES+)'],
    ('MFH', 'delna'): ['izolacija fasade', 'zamenjava oken'],
    ('MFH', 'celovita'): ['izolacija fasade in strehe', 'zamenjava oken', 'prezračevanje z vračanjem toplote', 'ogrevanje ostane daljinsko'],
}
NAME = {'delna': 'Delna prenova', 'celovita': 'Celovita prenova', 'zeb': 'Celovita ZEB prenova'}


def _surs_prices() -> dict:
    """SURS H028S: elektrika in zemeljski plin za gospodinjstva [EUR/kWh], kurilno olje [EUR/1000 l]; povprečje četrtletij 2025."""
    if CACHE.exists():
        return json.loads(CACHE.read_text(encoding='utf-8'))
    q = {'query': [{'code': 'ENERGENT', 'selection': {'filter': 'item', 'values': ['1', '3', '7']}},
                   {'code': 'ČETRTLETJE', 'selection': {'filter': 'item', 'values': ['2025Q1', '2025Q2', '2025Q3', '2025Q4']}}],
         'response': {'format': 'json'}}
    req = urllib.request.Request('https://pxweb.stat.si/SiStatData/api/v1/sl/Data/H028S.px', data=json.dumps(q).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'})
    d = json.load(urllib.request.urlopen(req, timeout=60))
    v = {}
    for r in d['data']:
        v.setdefault(r['key'][0], []).append(float(r['values'][0]))
    out = {'elektrika': round(np.mean(v['1']), 4), 'plin': round(np.mean(v['3']), 4), 'kurilno_olje': round(np.mean(v['7']) / 1000 / KWH_PER_L_OLJE, 4),
           'vir': 'SURS, tabela H028S Cene energentov (gospodinjski odjemalci), povprečje četrtletij 2025; kurilno olje preračunano s 10 kWh/l'}
    CACHE.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    return out


def _eko_costs(ctx: Context) -> dict:
    """€/m² po paketih iz Eko sklada: dejanske kombinacije ukrepov pri isti stavbi (2023–2025) in celovita obnova 2024–2025."""
    n = pd.read_excel(ctx.files['eko_stroski'], sheet_name='Nalozbe')
    n['k'] = n['KO-stavba|del'].astype(str).str.split('|').str[0]
    a_col, e_col = 'Ogrevana uporabna površina [m²]', 'Priznani stroški [EUR]'
    out = {}
    for tip in ('SFH', 'MFH'):
        s = n[n.Tip == tip]
        p = s.pivot_table(index='k', columns='Ukrep (koda)', values=e_col, aggfunc='sum')
        a = s.groupby('k')[a_col].first()

        def combo(cols, any_of=()):
            cols = [c for c in cols if c in p]
            m = p[cols].notna().all(axis=1)
            if any_of:
                m &= p[[c for c in any_of if c in p]].notna().any(axis=1)
            v = (p.loc[m, cols + [c for c in any_of if c in p]].sum(axis=1) / a[m])[a[m] >= 40].dropna()
            return v
        def per(cols):  # mediana posameznih ukrepov (na naložbo)
            return sum(s.loc[s['Ukrep (koda)'] == c, 'EUR/m²'].median() for c in cols)
        d = combo(['fasada', 'okna_vrata'])
        out[(tip, 'delna')] = (d, 'dejanske kombinacije fasada + okna pri isti stavbi') if len(d) >= 30 else (None, None)
        c = combo(['fasada', 'okna_vrata', 'streha'], ('tczv', 'tczemlja', 'tcvv'))
        out[(tip, 'celovita')] = (c, 'dejanske kombinacije fasada + okna + streha + toplotna črpalka pri isti stavbi') if len(c) >= 30 else (None, None)
        out[(tip, 'sum_delna')] = per(['fasada', 'okna_vrata'])
        out[(tip, 'sum_celovita_dh')] = per(['fasada', 'okna_vrata', 'streha', 'prezrac_lok'])
        out[(tip, 'prezr_centr')] = s.loc[s['Ukrep (koda)'] == 'prezrac_centr', 'EUR/m²'].median()
        z = s[(s['Ukrep (koda)'] == 'celovita_prenova') & (s.Leto >= 2024)]['EUR/m²'].dropna()
        out[(tip, 'zeb')] = (z, 'ukrep Eko sklada »celovita obnova stanovanjske stavbe« 2024–2025') if len(z) >= 5 else (None, None)
        out[(tip, 'zeb_spodbuda')] = (s.loc[s['Ukrep (koda)'] == 'celovita_prenova', 'Spodbuda [EUR]'].sum() / s.loc[s['Ukrep (koda)'] == 'celovita_prenova', e_col].sum()) if (s['Ukrep (koda)'] == 'celovita_prenova').any() else None
    return out


def build(ctx: Context) -> dict:
    from .stavbe import build_table
    df = build_table(ctx)
    fond = json.loads((DATA_DIR.parent / 'public' / 'data' / 'stavbni_fond.json').read_text(encoding='utf-8'))
    prih = json.loads((DATA_DIR.parent / 'public' / 'data' / 'prihranek.json').read_text(encoding='utf-8'))
    thr43 = {c['id']: c['worst_43']['threshold'] for c in fond['categories'] if c.get('worst_43')}
    bnd = {c['id']: [c['class_bounds'][k] for k in ('A|B', 'B|C', 'C|D', 'D|E', 'E|F', 'F|G')] for c in fond['categories']}
    cls = lambda cat, v: 'ABCDEFG'[sum(v > b for b in bnd[cat])]
    FE = {'SFH': {r['class']: r['sfh_use'] for r in prih['rows']}, 'MFH': {r['class']: r['mfh_use'] for r in prih['rows']}}
    for t, k in (('SFH', 'sfh'), ('MFH', 'mfh')):
        FE[t]['B1'] = prih['after'][k]
        FE[t]['B2'] = round((FE[t]['C'] + FE[t]['B1']) / 2)
    ORDER = ['G', 'F', 'E', 'D', 'C', 'B2', 'B1']
    prices = _surs_prices()
    ctx.check(0.1 < prices['elektrika'] < 0.4 and 0.05 < prices['kurilno_olje'] < 0.2, f'cene SURS 2025: {prices}')
    eko = _eko_costs(ctx)

    # stanje pred: neprenovljene stavbe z računsko izkaznico
    r = df[df.cat.isin(['HISA', 'BLOKI']) & df.ei_pe.notna() & df.ei_razred.notna()].copy()
    y = lambda c: pd.to_numeric(r[c], errors='coerce')
    ren = (y('obnova_fasada') >= 2010) | r.es_ovoj.notna() | (y('obnova_okna') >= 2010) | r.es_okna.notna()
    r = r[~ren]
    r['pg'] = r.period.astype(str).map(GRP)
    HC = ['A1', 'A2', 'B1', 'B2', 'C', 'D', 'E', 'F', 'G']

    q = Q_B1 / ETA + DHW
    tipi = []
    for tid, ime, t, pg, ogr in TYPES:
        cat = 'HISA' if t == 'SFH' else 'BLOKI'
        g = r[(r.cat == cat) & (r.pg == pg)]
        ctx.check(len(g) >= 500, f'paketi: {tid} ima {len(g)} izkaznic')
        pe0 = float(g.ei_pe.median())
        hc = sorted(g.ei_razred, key=HC.index)[len(g) // 2]  # mediana razreda toplotnih potreb
        hc = hc if hc in FE[t] else ('C' if HC.index(hc) < HC.index('C') else hc)
        area = float(df[(df.cat == cat) & df.period.astype(str).map(GRP).eq(pg)].m2.median()) if t == 'SFH' else \
            float((lambda b: b.m2.sum() / b.n_stan.sum())(df[(df.cat == cat) & df.period.astype(str).map(GRP).eq(pg)]))
        fe0 = FE[t][hc]
        price0 = prices['kurilno_olje'] if ogr == 'kurilno olje' else DH_EUR_KWH
        paketi = []
        for pid in ('delna', 'celovita', 'zeb'):
            if (t, pid) not in UKREPI:
                paketi.append({'id': pid, 'ime': NAME[pid], 'na_voljo': False,
                               'opomba': 'Za večstanovanjske stavbe Eko sklad nima podatkov o celoviti ZEB prenovi; ocene ni.'})
                continue
            v, src = eko.get((t, pid), (None, None))
            if pid == 'celovita' and t == 'SFH' and v is not None:
                v = v + eko[(t, 'prezr_centr')]
                src += ' + centralno prezračevanje (mediana)'
            if v is not None:
                eur, p25, p75, nn = float(v.median()), float(v.quantile(.25)), float(v.quantile(.75)), int(len(v))
            else:
                eur = float(eko[(t, 'sum_delna' if pid == 'delna' else 'sum_celovita_dh')]); p25 = p75 = None; nn = None
                src = 'vsota median posameznih ukrepov (premalo dejanskih kombinacij)'
            if pid == 'delna':
                h1 = ORDER[min(ORDER.index(hc) + 2, ORDER.index('B2'))]
                fe1 = FE[t][h1]; pe1 = pe0 * fe1 / fe0
                cost1 = fe1 * price0
            elif t == 'SFH':  # toplotna črpalka
                el = q / SCOP + AUX
                fe1 = q + AUX
                pe1 = q / SCOP * FP['el'] + q * (1 - 1 / SCOP) * FP['amb'] + AUX * FP['el']
                if pid == 'zeb':
                    pe1 *= (1 - PV_SHARE); el *= (1 - PV_SHARE)
                cost1 = el * prices['elektrika']
            else:  # blok ostane na daljinskem ogrevanju
                fe1 = q + AUX
                pe1 = q * FP['dh'] + AUX * FP['el']
                cost1 = q * DH_EUR_KWH + AUX * prices['elektrika']
            cost = eur * area
            sav = (fe0 * price0 - cost1) * area
            # N1 (preglednica 26): razred E +10, razreda F in G oziroma stavbe nad pragom 43 % +20 odstotnih točk (razred NPS pred prenovo)
            c0 = cls(cat, pe0)
            above = pe0 > thr43[cat]
            bonus = 20 if (c0 in ('F', 'G') or above) else 10 if c0 == 'E' else 0
            s_osn = 30 + (10 if pid != 'delna' else 0)
            s_dod = min(70, s_osn + bonus)
            pb = lambda s: round(cost * (1 - s / 100) / sav, 1) if sav > 0 else None
            paketi.append({
                'id': pid, 'ime': NAME[pid], 'na_voljo': True, 'ukrepi': UKREPI[(t, pid)],
                'eur_m2': round(eur), 'eur_m2_p25': round(p25) if p25 else None, 'eur_m2_p75': round(p75) if p75 else None, 'n': nn, 'vir_stroska': src,
                'strosek': round(cost, -2), 'razred_po': cls(cat, pe1), 'pe_po': round(pe1), 'fe_po': round(fe1),
                'prihranek_fe_pct': round(100 * (fe0 - fe1) / fe0), 'prihranek_pe_pct': round(100 * (pe0 - pe1) / pe0),
                'prihranek_eur': round(sav, -1), 'spodbuda_osn_pct': s_osn, 'spodbuda_dod_pct': s_dod, 'spodbuda_dod_eur': round(cost * s_dod / 100, -2),
                'spodbuda_razlog': 'stavba je med 43 % energetsko najmanj učinkovitih' if above else (f'razred {c0}' if bonus else None),
                'vracilo_brez': pb(0), 'vracilo_osn': pb(s_osn), 'vracilo_dod': pb(s_dod),
            })
        cel = next(p for p in paketi if p['id'] == 'celovita')
        ctx.check(cel['razred_po'] == 'A', f'paketi: celovita prenova {tid} doseže razred A ({cel["pe_po"]} kWh/(m²·a))')
        tipi.append({'id': tid, 'ime': ime, 'tip': t, 'ogrevanje_pred': ogr, 'povrsina': round(area), 'razred_toplota_pred': hc,
                     'razred_pred': cls(cat, pe0), 'pe_pred': round(pe0), 'fe_pred': fe0, 'n_izkaznic': int(len(g)), 'paketi': paketi})

    data = {
        'meta': ctx.meta(['Eko sklad, priznani stroški naložb 2023–2025 (analiza IJS CEU, 2. 10. 2026)', prices['vir'], DH_VIR,
                          f'{ctx.draft.name}: preglednica 23 (raba končne energije po razredih), preglednica 26 (predlog spodbud N1), meje razredov',
                          'Register energetskih izkaznic in kataster nepremičnin (stanje pred prenovo)'],
                         note='Tipične vrednosti za ponazoritev, ne izračun za konkretno stavbo.'),
        'cene': {'kurilno_olje': prices['kurilno_olje'], 'elektrika': prices['elektrika'], 'plin': prices['plin'], 'daljinska_toplota': DH_EUR_KWH},
        'predpostavke': {'q_b1': Q_B1, 'eta': ETA, 'topla_voda': DHW, 'scop': SCOP, 'pomozna_el': AUX, 'fp': FP, 'pv_delez': PV_SHARE,
                         'zeb_spodbuda_dejanska_pct': round(100 * eko[('SFH', 'zeb_spodbuda')]) if eko[('SFH', 'zeb_spodbuda')] else None},
        'tipi': tipi,
    }
    write_json('paketi_prenove', data)
    return data
