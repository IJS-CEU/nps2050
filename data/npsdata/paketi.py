"""11.4 Tipični paketi prenove s stroški: delna, celovita prenova ovoja in sistemov (do razreda A po primarni energiji)
in prenova do skoraj nič-energijske stavbe (sNES).

Viri (potrdil Gašper 2. 10. 2026):
- stroški: Eko sklad 2023–2025, priznani stroški na m² ogrevane uporabne površine po GURS (analiza Stroski_EUR_m2);
  delna in celovita prenova iz dejanskih kombinacij ukrepov pri isti stavbi (seštevek priznanih stroškov ukrepov, ne sNES);
  prenova do sNES (glavni vir Eko sklad, odločitev 4. 10. 2026): ukrepa »celovita obnova stanovanjske stavbe« in
  »sNES+ prenova« 2022–2025, priznani stroški na m² ogrevane površine iz vloge, za tipično hišo × kondicionirana površina iz izkaznic;
- vsi stroški so PRIZNANI stroški Eko sklada (z DDV, nominalno); dejanska naložba je višja (projektiranje, neupravičena dela,
  potresna utrditev, prenova inštalacij); prikazan je razpon 25.–75. percentila;
- raba končne energije po razredih toplotnih potreb: osnutek, preglednica 23 (model RenRates) – za učinek delne prenove;
- stanje pred prenovo: mediana primarne energije neprenovljenih stavb z računsko izkaznico po glavnem ogrevanju;
  tipična površina: mediana kondicionirane površine iz izkaznic (hiše) oziroma povprečna površina stanovanja (bloki);
- cene energentov za gospodinjstva: SURS (tabela H028S, povprečje četrtletij 2025); drva: Gozdarski inštitut Slovenije;
  daljinska toplota: Agencija za energijo, Analiza cen toplote 2025;
- spodbude: predlog ukrepa N1 (osnutek, preglednica 26).
"""
import json
import urllib.request

import numpy as np
import pandas as pd

from .context import DATA_DIR, Context, write_json

CACHE = DATA_DIR / 'raw' / 'surs_cene_2025.json'
KWH_PER_L_OLJE = 10.0           # kurilna vrednost ekstra lahkega kurilnega olja, kWh/l
WOOD_EUR_KWH = round(195 / 4000, 3)  # drva: 195 €/t (Gozdarski inštitut Slovenije, oktober 2024), 4,0 kWh/kg (zračno suha drva)
WOOD_VIR = 'Gozdarski inštitut Slovenije, cene lesnih goriv (drva, oktober 2024: 195 €/t), preračunano s 4,0 kWh/kg'
DH_EUR_KWH = 0.16998            # Agencija za energijo, Analiza cen toplote 2025: GJS, 69 m² stanovanje, s prispevki in DDV
DH_VIR = 'Agencija za energijo, Analiza cen toplote iz distribucijskih sistemov za leto 2025 (povprečje GJS, značilni odjemalec v večstanovanjski stavbi, s prispevki in DDV)'
# stanje po celoviti prenovi
Q_B1, ETA, DHW, SCOP, AUX = 20.0, 0.9, 15.0, 3.5, 3.0
FP = {'el': 2.5, 'amb': 1.0, 'olje': 1.1, 'plin': 1.1, 'les': 1.2, 'dh': 1.23}  # faktorji skupne primarne energije (zakonski 2025, kot v osnutku)
LIFE = 30                                                 # življenjska doba prenove za strošek prihranjene kWh [let]
PV_SHARE = 0.4                                            # ZEB: delež letne rabe elektrike, pokrit s sončno elektrarno na stavbi
GRP = {'do 1945': 'do1980', '1946–1970': 'do1980', '1971–1980': 'do1980', '1981–1990': '1981_2002', '1991–2002': '1981_2002'}
TYPES = [
    ('hisa_do1980', 'Enodružinska hiša, zgrajena do leta 1980', 'SFH', 'do1980', ['olje', 'plin', 'les']),
    ('hisa_1981_2002', 'Enodružinska hiša, zgrajena 1981–2002', 'SFH', '1981_2002', ['olje', 'plin', 'les']),
    ('blok_do1980', 'Stanovanje v bloku, zgrajenem do leta 1980', 'MFH', 'do1980', ['daljinsko']),
    ('blok_1981_2002', 'Stanovanje v bloku, zgrajenem 1981–2002', 'MFH', '1981_2002', ['daljinsko']),
]
UKREPI = {
    ('SFH', 'delna'): ['izolacija fasade', 'zamenjava oken'],
    ('SFH', 'celovita'): ['izolacija fasade in strehe', 'zamenjava oken', 'toplotna črpalka', 'prezračevanje z vračanjem toplote'],
    ('SFH', 'zeb'): ['celovita prenova ovoja in sistemov', 'izolacija tal', 'sončna elektrarna', 'zahteve skoraj nič-energijske stavbe (Eko sklad)'],
    ('MFH', 'delna'): ['izolacija fasade', 'zamenjava oken'],
    ('MFH', 'celovita'): ['izolacija fasade in strehe', 'zamenjava oken', 'prezračevanje z vračanjem toplote', 'ogrevanje ostane daljinsko'],
}
# Veljavna javna poziva Eko sklada: (delež, zgornja meja na enoto, enot na m² ogrevane površine ali None za mejo na stavbo,
# upravičeni stroški brez DDV). Količine ukrepov na m² ogrevane površine: mediane naložb Eko sklada 2023–2025.
POZIV = {'SFH': 'Javni poziv Eko sklada 126SUB-OB26 (eno- in dvostanovanjske stavbe)',
         'MFH': 'Javna poziva Eko sklada 124SUB-OBPO25 (skupni deli stavb z najmanj tremi deli) in 126SUB-OB26 (okna in prezračevanje v stanovanju)'}
POZIV_UKREPI = {
    'SFH': {
        'fasada': (0.40, 35, 2.09, False),          # 126 F: do 40 %, največ 35 €/m² izolacije
        'okna_vrata': (0.40, 300, 0.142, False),    # 126 E: do 40 %, največ 300 €/m² oken (samo lesena okna)
        'streha': (0.40, 35, 0.91, False),          # 126 G: do 40 %, največ 35 €/m² izolacije
        'tczv': (0.50, 4500, None, False),          # 126 C: zamenjava stare kurilne naprave, do 50 %, največ 4.500 €
        'prezrac_centr': (0.30, 2500, None, False),  # 126 I: centralno prezračevanje, do 30 %, največ 2.500 €
    },
    'MFH': {
        'fasada': (0.30, 50, 0.976, True),          # 124 A: do 30 % upravičenih stroškov brez DDV, največ 50 €/m² izolacije
        'streha': (0.30, 50, 0.263, True),          # 124 B: do 30 %, največ 50 €/m² ravne strehe (25 €/m² poševne)
        'okna_vrata': (0.40, 300, 0.154, False),    # 126 E: lesena okna v stanovanju, do 40 %, največ 300 €/m² oken
        'prezrac_lok': (0.30, 600, 0.038, False),   # 126 I: lokalno prezračevanje, do 30 %, največ 600 € na napravo
    },
}
PAKET_UKREPI = {('SFH', 'delna'): ['fasada', 'okna_vrata'], ('SFH', 'celovita'): ['fasada', 'okna_vrata', 'streha', 'tczv', 'prezrac_centr'],
                ('MFH', 'delna'): ['fasada', 'okna_vrata'], ('MFH', 'celovita'): ['fasada', 'okna_vrata', 'streha', 'prezrac_lok']}
NAME = {'delna': 'Delna prenova', 'celovita': 'Celovita prenova ovoja in sistemov', 'zeb': 'Prenova do skoraj nič-energijske stavbe (sNES)'}
SNES_OD = 2022  # sNES: projekti od tega leta (novejše cene, dovolj primerov)
HC = ['A1', 'A2', 'B1', 'B2', 'C', 'D', 'E', 'F', 'G']


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
            return (p.loc[m, cols + [c for c in any_of if c in p]].sum(axis=1) / a[m])[a[m] >= 40].dropna()

        def per(cols):  # vsota median posameznih ukrepov
            return sum(s.loc[s['Ukrep (koda)'] == c, 'EUR/m²'].median() for c in cols)
        # dejanski delež spodbude Eko sklada 2025 za iste ukrepe (vsota spodbud / vsota priznanih stroškov ukrepov paketa)
        s25 = s[s.Leto == 2025]
        g25 = s25.groupby('Ukrep (koda)')[[e_col, 'Spodbuda [EUR]']].sum()
        def share(cols):
            cols = [c for c in cols if c in g25.index]
            return float(g25.loc[cols, 'Spodbuda [EUR]'].sum() / g25.loc[cols, e_col].sum()) if cols else None
        out[(tip, 'eko25_delna')] = share(['fasada', 'okna_vrata'])
        out[(tip, 'med')] = {u: float(s.loc[s['Ukrep (koda)'] == u, 'EUR/m²'].median()) for u in POZIV_UKREPI[tip]}
        out[(tip, 'eko25_celovita')] = share(['fasada', 'okna_vrata', 'streha', 'tczv', 'prezrac_centr'] if tip == 'SFH' else ['fasada', 'okna_vrata', 'streha', 'prezrac_lok'])
        cz = s[(s['Ukrep (koda)'] == 'celovita_prenova') & (s.Leto >= 2024)]
        out[(tip, 'eko25_zeb')] = float(cz['Spodbuda [EUR]'].sum() / cz[e_col].sum()) if len(cz) else None
        d = combo(['fasada', 'okna_vrata'])
        out[(tip, 'delna')] = (d, 'dejanske kombinacije fasada + okna pri isti stavbi') if len(d) >= 30 else (None, None)
        c = combo(['fasada', 'okna_vrata', 'streha'], ('tczv', 'tczemlja', 'tcvv'))
        out[(tip, 'celovita')] = (c, 'dejanske kombinacije fasada + okna + streha + toplotna črpalka pri isti stavbi') if len(c) >= 30 else (None, None)
        out[(tip, 'sum_delna')] = per(['fasada', 'okna_vrata'])
        out[(tip, 'sum_celovita_dh')] = per(['fasada', 'okna_vrata', 'streha', 'prezrac_lok'])
        out[(tip, 'prezr_centr')] = s.loc[s['Ukrep (koda)'] == 'prezrac_centr', 'EUR/m²'].median()
        z = s[(s['Ukrep (koda)'] == 'celovita_prenova') & (s.Leto >= 2024)]['EUR/m²'].dropna()
        out[(tip, 'zeb')] = (z, 'ukrep Eko sklada »celovita obnova stanovanjske stavbe« 2024–2025') if len(z) >= 5 else (None, None)
        cp = s['Ukrep (koda)'] == 'celovita_prenova'
        out[(tip, 'zeb_spodbuda')] = (s.loc[cp, 'Spodbuda [EUR]'].sum() / s.loc[cp, e_col].sum()) if cp.any() else None
    return out


def _snes_costs(ctx: Context):
    """Eko sklad: »celovita obnova stanovanjske stavbe« in »sNES+ prenova« od SNES_OD dalje; priznani stroški na m² ogrevane
    površine iz vloge (SumOfKolicina, m²). Vrne (€/m² po projektih, dejanski delež spodbude)."""
    frames = [pd.read_excel(ctx.files['es_2025'], sheet_name='Podatki').assign(L=2025)]
    for y in range(SNES_OD, 2025):
        frames.append(pd.read_excel(ctx.files['es_letni'], sheet_name=str(y)).assign(L=y))
    d = pd.concat(frames)
    x = d[d.Parameter.astype(str).str.contains(r'celovita obnova|sNES\+ prenova', case=False)].copy()
    num = lambda v: pd.to_numeric(v.astype(str).str.replace(',', '.'), errors='coerce')
    for k in ('PriznaniStroski', 'ZnesekSpodbude', 'SumOfKolicina', 'TipStavbe'):
        x[k] = num(x[k])
    x = x[x.TipStavbe.isin([1, 2, 3, 4, 5, 19]) & x.SumOfKolicina.between(50, 1000)]
    ctx.check(len(x) >= 25, f'paketi: sNES iz {len(x)} projektov Eko sklada {SNES_OD}–2025')
    return x.PriznaniStroski / x.SumOfKolicina, float(x.ZnesekSpodbude.sum() / x.PriznaniStroski.sum())


def _areas(ctx: Context, df: pd.DataFrame) -> dict:
    """(površina za energijo, površina za stroške): hiše – mediana kondicionirane površine iz računskih izkaznic (cela stavba)
    in mediana uporabne površine po katastru za iste stavbe; bloki – površina stanovanja (kataster) in preračun na izkaznico."""
    ei = pd.read_csv(ctx.files['ei_stanje'], sep='|', dtype=str, usecols=['Šifra KO', 'Številka stavbe', 'Tip izkaznice', 'Kondicionirana površina stavbe'])
    ei = ei[ei['Tip izkaznice'].str.strip() == 'računska']
    ei['key'] = ei['Šifra KO'].str.strip().str.lstrip('0') + '-' + ei['Številka stavbe'].str.strip().str.lstrip('0')
    ei['A'] = pd.to_numeric(ei['Kondicionirana površina stavbe'].str.replace(',', '.'), errors='coerce')
    e = ei.groupby('key').A.max()
    out = {}
    for cat in ('HISA', 'BLOKI'):
        b = df[df.cat == cat].copy()
        b['pg'] = b.period.astype(str).map(GRP)
        m = b.join(e, on='key')
        for pg in ('do1980', '1981_2002'):
            g = m[(m.pg == pg) & m.A.between(20, 20000)]
            if cat == 'HISA':
                ctx.check(len(g) >= 500, f'paketi: površine {cat}/{pg} iz {len(g)} izkaznic')
                out[(cat, pg)] = (float(g.A.median()), float(g.m2.median()))
            else:
                k = b[b.pg == pg]
                per_flat = float(k.m2.sum() / k.n_stan.sum())
                out[(cat, pg)] = (per_flat, per_flat)  # izkaznice blokov so pogosto za dele stavb, zato površina stanovanja iz katastra
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
    snes, snes_spodbuda = _snes_costs(ctx)
    eko[('SFH', 'zeb')] = (snes, f'Eko sklad: celovita obnova stanovanjske stavbe in sNES+ prenova {SNES_OD}–2025, priznani stroški na m² ogrevane površine iz vloge')
    eko[('SFH', 'eko25_zeb')] = snes_spodbuda
    eko[('SFH', 'zeb_spodbuda')] = snes_spodbuda
    area = _areas(ctx, df)
    # dejanska raba po modelu občin (usklajena z bilanco), na m² uporabne površine po katastru
    mfe = json.loads((DATA_DIR / 'raw' / 'model_fe_tipi.json').read_text(encoding='utf-8'))

    # stanje pred: neprenovljene stavbe z računsko izkaznico; glavno ogrevanje iz deležev energentov v izkaznici
    r = df[df.cat.isin(['HISA', 'BLOKI']) & df.ei_pe.notna() & df.ei_razred.notna()].copy()
    y = lambda c: pd.to_numeric(r[c], errors='coerce')
    ren = (y('obnova_fasada') >= 2010) | r.es_ovoj.notna() | (y('obnova_okna') >= 2010) | r.es_okna.notna()
    r = r[~ren]
    r['pg'] = r.period.astype(str).map(GRP)
    sh = r[['ei_sh_gas', 'ei_sh_elko', 'ei_sh_bio', 'ei_sh_dh', 'ei_sh_el']].rename(columns=lambda c: c[6:])
    r['ogr'] = np.where(r.ei_sh_amb >= 0.15, 'tc', sh.idxmax(axis=1))

    q = Q_B1 / ETA + DHW
    OGR = {'olje': ('kurilno olje', 'elko', prices['kurilno_olje'], FP['olje']), 'plin': ('zemeljski plin', 'gas', prices['plin'], FP['plin']),
           'les': ('les (drva)', 'bio', WOOD_EUR_KWH, FP['les']), 'daljinsko': ('daljinsko ogrevanje', 'dh', DH_EUR_KWH, FP['dh'])}
    tipi, faktor = [], {}
    for tid, ime, t, pg, ogr_list in TYPES:
        cat = 'HISA' if t == 'SFH' else 'BLOKI'
        a_ei, a_kat = area[(cat, pg)]
        variante = []
        for oid in ogr_list:
            oname, code, price0, fp0 = OGR[oid]
            g = r[(r.cat == cat) & (r.pg == pg) & (r.ogr == code)]
            ctx.check(len(g) >= 100, f'paketi: {tid}/{oid} ima {len(g)} izkaznic')
            pe0 = float(g.ei_pe.median())        # razred na izkaznici (računska raba)
            m = mfe[f'{cat}|{pg}|{code}']
            ctx.check(m['n'] >= 500, f'paketi: model {cat}/{pg}/{code} {m["n"]} stavb')
            fe0 = m['fe_kwh_m2']                 # dejanska raba končne energije na m² (kataster)
            hc = sorted(g.ei_razred, key=HC.index)[len(g) // 2]
            hc = hc if hc in FE[t] else 'C'
            paketi = []
            for pid in ('delna', 'celovita', 'zeb'):
                if (t, pid) not in UKREPI:
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
                # stanje po prenovi: energija na m² površine po katastru (računska raba celovite prenove je na m² izkaznice)
                k_a = a_ei / a_kat
                if pid == 'delna':
                    h1 = ORDER[min(ORDER.index(hc) + 2, ORDER.index('B2'))]
                    rr = FE[t][h1] / FE[t][hc]
                    fe1, pe1 = fe0 * rr, pe0 * rr
                    cost1 = fe1 * price0
                    buy1 = fe1
                    faktor.setdefault(cat, []).append(rr)
                elif t == 'SFH':  # toplotna črpalka
                    el = (q / SCOP + AUX) * k_a
                    fe1 = (q + AUX) * k_a
                    pe1 = q / SCOP * FP['el'] + q * (1 - 1 / SCOP) * FP['amb'] + AUX * FP['el']
                    if pid == 'zeb':
                        pe1 *= (1 - PV_SHARE); el *= (1 - PV_SHARE)
                    cost1 = el * prices['elektrika']
                    buy1 = el
                else:  # blok ostane na daljinskem ogrevanju
                    fe1 = (q + AUX) * k_a
                    pe1 = q * FP['dh'] + AUX * FP['el']
                    cost1 = (q * DH_EUR_KWH + AUX * prices['elektrika']) * k_a
                    buy1 = (q + AUX) * k_a
                # strošek: delna in celovita na m² ogrevane površine po katastru (kot analiza Eko sklada), sNES na m² površine iz vloge
                # (≈ kondicionirana površina iz izkaznic); energija na m² kondicionirane površine iz izkaznic
                a_cost = a_ei if pid == 'zeb' else a_kat
                cost = eur * a_cost
                sav = (fe0 * price0 - cost1) * a_kat
                # spodbuda po veljavnih pozivih (delna in celovita prenova): stroški ukrepov sorazmerno z medianami Eko sklada
                poziv_eur = None
                if (t, pid) in PAKET_UKREPI:
                    us = PAKET_UKREPI[(t, pid)]
                    med = eko[(t, 'med')]
                    tot = sum(med[u] for u in us)
                    poziv_eur = 0.0
                    for u in us:
                        cu = cost * med[u] / tot
                        pct, cap, q_m2, neto = POZIV_UKREPI[t][u]
                        poziv_eur += min(pct * cu / (1.22 if neto else 1), cap * q_m2 * a_kat if q_m2 else cap)
                c0 = cls(cat, pe0)
                above = pe0 > thr43[cat]
                bonus = 20 if (c0 in ('F', 'G') or above) else 10 if c0 == 'E' else 0
                s_osn = 30 + (10 if pid != 'delna' else 0)
                s_dod = min(70, s_osn + bonus)
                pb = lambda s_: round(cost * (1 - s_ / 100) / sav, 1) if sav > 0 else None
                saved_kwh = (fe0 - buy1) * a_kat     # manj kupljene energije na leto
                ekwh = lambda s_: round(cost * (1 - s_ / 100) / (saved_kwh * LIFE), 3) if saved_kwh > 0 else None
                paketi.append({
                    'id': pid, 'ime': NAME[pid], 'na_voljo': True, 'ukrepi': UKREPI[(t, pid)],
                    'eur_m2': round(eur), 'eur_m2_p25': round(p25) if p25 else None, 'eur_m2_p75': round(p75) if p75 else None, 'n': nn, 'vir_stroska': src,
                    'strosek': round(cost, -2), 'strosek_p25': round(p25 * a_cost, -2) if p25 else None, 'strosek_p75': round(p75 * a_cost, -2) if p75 else None,
                    'povrsina_stroska': round(a_cost), 'razred_po': cls(cat, pe1), 'pe_po': round(pe1), 'fe_po': round(fe1),
                    'prihranek_fe_pct': round(100 * (fe0 - fe1) / fe0), 'prihranek_pe_pct': round(100 * (pe0 - pe1) / pe0),
                    'fe_pred_leto': round(fe0 * a_kat, -2), 'fe_po_leto': round(fe1 * a_kat, -2), 'stroski_pred_leto': round(fe0 * a_kat * price0, -1),
                    'prihranek_eur': round(sav, -1), 'spodbuda_osn_pct': s_osn, 'spodbuda_dod_pct': s_dod, 'spodbuda_dod_eur': round(cost * s_dod / 100, -2),
                    'spodbuda_razlog': 'stavba je med 43 % energetsko najmanj učinkovitih' if above else (f'razred {c0}' if bonus else None),
                    'vracilo_brez': pb(0), 'vracilo_osn': pb(s_osn), 'vracilo_dod': pb(s_dod),
                    'spodbuda_eko_pct': round(100 * poziv_eur / cost) if poziv_eur is not None else (round(100 * eko[(t, f'eko25_{pid}')]) if eko.get((t, f'eko25_{pid}')) else None),
                    'spodbuda_eko_eur': round(poziv_eur, -2) if poziv_eur is not None else (round(cost * eko[(t, f'eko25_{pid}')], -2) if eko.get((t, f'eko25_{pid}')) else None),
                    'spodbuda_eko_vir': 'poziv' if poziv_eur is not None else 'dejansko 2025',
                    'eur_kwh_eko': ekwh(100 * poziv_eur / cost) if poziv_eur is not None else (ekwh(100 * eko[(t, f'eko25_{pid}')]) if eko.get((t, f'eko25_{pid}')) else None),
                    'prihranjeno_kwh_leto': round(saved_kwh, -2), 'eur_kwh_brez': ekwh(0), 'eur_kwh_dod': ekwh(s_dod), 'cena_energije_pred': price0,
                })
            cel = next(p for p in paketi if p['id'] == 'celovita')
            ctx.check(cel['razred_po'] == 'A', f'paketi: celovita prenova {tid}/{oid} doseže razred A ({cel["pe_po"]} kWh/(m²·a))')
            variante.append({'id': oid, 'ogrevanje': oname, 'razred_pred': cls(cat, pe0), 'pe_pred': round(pe0), 'fe_pred': round(fe0),
                             'razred_toplota_pred': hc, 'n_izkaznic': int(len(g)), 'paketi': paketi})
        tipi.append({'id': tid, 'ime': ime, 'tip': t, 'povrsina': round(a_ei), 'povrsina_kataster': round(a_kat), 'variante': variante})

    # za orodje Preveri stavbo: stanje po prenovi stavbe z izkaznico
    pe_cel_sfh = q / SCOP * FP['el'] + q * (1 - 1 / SCOP) * FP['amb'] + AUX * FP['el']
    preveri = {'HISA': {'delna_faktor': round(float(np.median(faktor['HISA'])), 2), 'celovita_pe': round(pe_cel_sfh), 'zeb_pe': round(pe_cel_sfh * (1 - PV_SHARE))},
               'BLOKI': {'delna_faktor': round(float(np.median(faktor['BLOKI'])), 2), 'celovita_pe': round(q * FP['dh'] + AUX * FP['el']), 'zeb_pe': None}}

    data = {
        'meta': ctx.meta(['Eko sklad, priznani stroški naložb 2023–2025 (analiza IJS CEU, 2. 10. 2026); sNES: celovite obnove in sNES+ prenove 2022–2025', prices['vir'], WOOD_VIR, DH_VIR,
                          f'{ctx.draft.name}: preglednica 23 (raba končne energije po razredih), preglednica 26 (predlog spodbud N1), meje razredov',
                          'Register energetskih izkaznic in kataster nepremičnin (stanje pred prenovo, površine)'],
                         note='Tipične vrednosti za ponazoritev, ne izračun za konkretno stavbo. Stroški so priznani stroški Eko sklada; dejanska naložba je višja.'),
        'cene': {'kurilno_olje': prices['kurilno_olje'], 'elektrika': prices['elektrika'], 'plin': prices['plin'], 'les': WOOD_EUR_KWH, 'daljinska_toplota': DH_EUR_KWH},
        'preveri': preveri,
        'poziv': POZIV,
        'predpostavke': {'zivljenjska_doba': LIFE, 'q_b1': Q_B1, 'eta': ETA, 'topla_voda': DHW, 'scop': SCOP, 'pomozna_el': AUX, 'fp': FP, 'pv_delez': PV_SHARE,
                         'zeb_spodbuda_dejanska_pct': round(100 * eko[('SFH', 'zeb_spodbuda')]) if eko[('SFH', 'zeb_spodbuda')] else None},
        'tipi': tipi,
    }
    write_json('paketi_prenove', data)
    return data
