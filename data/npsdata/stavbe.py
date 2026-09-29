"""Baza na ravni stavbe (NE objavi se): kataster + deli stavb + register izkaznic + Eko sklad.

Iz nje se računajo samo agregati po občinah (obcine.py) in modelska ocena (model_obcine.py).
Rezultat se shrani v data/raw/stavbe.pkl (data/raw je v .gitignore); ob spremembi virov se preračuna.
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

from .context import DATA_DIR, Context

CACHE = DATA_DIR / 'raw' / 'stavbe.pkl'

# Pretežna dejanska raba dela stavbe, ki stavbo uvrsti med javne (CLAUDE.md §10.1; šifrant VRSTE_DEJANSKIH_RAB_DEL_ST).
PUBLIC_USES = {8, 14, 22, 23, 24, 25, 26, 32, 41, 43, 44, 51}
# Pomožne rabe (garaža, parkirno mesto, skladišče, klet, shramba, balkon, tehnični in skupni prostori, kmetijski deli …)
# se pri določanju pretežne rabe ne štejejo; tako se število javnih stavb ujema s preglednico 3 osnutka (±0,2 %).
AUX_USES = {15, 16, 19, 20, 21, 27, 28, 29, 33, 34, 35, 36, 37, 38, 39, 40}
RES = {'HISA', 'BLOKI'}
PERIOD_EDGES = [1945, 1970, 1980, 1990, 2002, 2010, 2020]  # kot preglednici 10 in 11 osnutka
PERIODS = ['do 1945', '1946–1970', '1971–1980', '1981–1990', '1991–2002', '2003–2010', '2011–2020', 'po 2020']

# Faktorji primarne energije kot v Razredi_primarna_energija_MODEL.xlsx (list Faktorji_PE); šifre iz registra izkaznic.
# Energenti v masnih ali prostorninskih enotah (kg, m³, l) se ne upoštevajo.
_PE = {'e': 2.5, 'zp': 1.1, 'elko': 1.1, 'lb': 1.2, 'dt': 1.3, 'dolb': 1.61, 'do_ove': 1.0, 'do_spte_lb': 1.4, 'do_fos': 1.61,
       'dteu': 1.61, 'ge': 1.0, 'p': 1.1, 'se': 1.0, 'sse': 1.0, 'to': 1.0, 'unp': 1.1, 'bp': 1.4, 'spte': 0.0, 've': 1.0}
PE_FACTORS = {
    'energy_e': _PE['e'], 'ELEKTRIKA': _PE['e'], 'energy_zp': _PE['zp'], 'ZEMELJSKI_PLIN': _PE['zp'], 'ZEMELJSKI_PLIN_KWH': _PE['zp'],
    'energy_elko': _PE['elko'], 'EKSTRA_LAHKO_KURILNO_OLJE': _PE['elko'], 'KURILNO_OLJE': _PE['elko'], 'LAHKO_KURILNO_OLJE': _PE['elko'],
    'energy_lb': _PE['lb'], 'LESNA_BIOMASA': _PE['lb'], 'LESNA_BIOMASA_BRIKETI': _PE['lb'], 'LESNA_BIOMASA_PELETI': _PE['lb'],
    'LESNA_BIOMASA_POLENA': _PE['lb'], 'LESNA_BIOMASA_SEKANCI': _PE['lb'],
    'energy_dt': _PE['dt'], 'DALJINSKA_TOPLOTA': _PE['dt'], 'DALJINSKO_OGREVANJE_NEOBNOVLJIVI_VIRI_ENERGIJE': _PE['dt'],
    'energy_dtlb': _PE['dolb'], 'DALJINSKA_TOPLOTA_NA_LESNO_BIOMASO': _PE['dolb'],
    'DALJINSKA_TOPLOTA_OVE_NA_LESNO_BIOMASO': _PE['do_ove'], 'DALJINSKO_OGREVANJE_OVE_SONCNA_GEOTERMALNA_ENERGIJA': _PE['do_ove'],
    'GEOTERMALNA_VODA': _PE['do_ove'], 'DALJINSKO_OGREVANJE_OVE_SPTE_NA_BIOMASO': _PE['do_spte_lb'],
    'DALJINSKO_OGREVANJE_S_KOGENERACIJO': _PE['do_fos'], 'DALJINSKO_OGREVANJE_UCINKOVITO_OGREVANJE_IN_SPTE_NA_FOSILNA_GORIVA': _PE['do_fos'],
    'energy_dteu': _PE['dteu'], 'energy_ge': _PE['ge'], 'energy_p': _PE['p'], 'energy_se': _PE['se'], 'SONCNA_ELEKTRARNA': _PE['se'],
    'energy_sse': _PE['sse'], 'SPREJEMNIKI_SONCNE_ENERGIJE': _PE['sse'], 'energy_to': _PE['to'], 'TOPLOTA_OKOLJA_TC': _PE['to'],
    'energy_unp': _PE['unp'], 'BIOPLIN': _PE['bp'], 'SPTE_V_STAVBI_FOSILNO_GORIVO_ELEKTRIKA': _PE['spte'],
    'SPTE_V_STAVBI_FOSILNO_GORIVO_TOPLOTA': _PE['spte'], 'VETRNA_ELEKTRARNA': _PE['ve'],
}

# Eko sklad: vrste ukrepov (stolpci matrike do 2024 in vzorci imen parametrov 2025).
ES_GROUPS = {
    'ovoj': (['Ukrep_fasada', 'Ukrep_streha', 'Ukrep_kletna_izolacija', 'Ukrep_talna_izolacija'], r'Izolacija'),
    'okna': (['Ukrep_okna_vrata'], r'OKEN|OKNA'),
    'tc': (['Ukrep_tcvv', 'Ukrep_tczv', 'Ukrep_tci'], r'TČ Z|TČ V|Ele\.-TČ'),
    'biomasa': (['Ukrep_biomasa'], r'^BIOM'),
    'daljinsko': (['Ukrep_daljinsko'], r'Daljinsk'),
    'pv': (['Ukrep_fotovoltaika'], r'Fotovolt'),
    'prezr': (['Ukrep_prezrac'], r'Prezrač|Prez-'),
}


def _key(ko, st) -> pd.Series:
    ko = pd.to_numeric(ko, errors='coerce').astype('Int64').astype(str)
    st = pd.Series(st).astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
    return ko + '-' + st


def period(year: pd.Series) -> pd.Series:
    return pd.cut(year, [0, *PERIOD_EDGES, 3000], labels=PERIODS, right=True)


def build_table(ctx: Context, refresh: bool = False) -> pd.DataFrame:
    srcs = [ctx.files[k] for k in ('kataster_stavbe', 'deli_stavb', 'ei_stanje', 'ei_energenti', 'es_matrika', 'es_2025')]
    if CACHE.exists() and not refresh and CACHE.stat().st_mtime > max(Path(p).stat().st_mtime for p in srcs):
        return pd.read_pickle(CACHE)

    ks = pd.read_csv(ctx.files['kataster_stavbe'], dtype={'EID_STAVBA': str, 'EID_OBCINA': str})
    ks['EID_OBCINA'] = ks['EID_OBCINA'].str.replace(r'\.0$', '', regex=True)
    ks = ks[ks.UPORABNA_POVRSINA_EPBD > 0].copy()
    ks['key'] = _key(ks.KO_ID, ks.ST_STAVBE)
    df = ks.rename(columns={'EPBD': 'cat', 'UPORABNA_POVRSINA_EPBD': 'm2', 'LETO_IZGRA': 'year', 'EID_OBCINA': 'obcina',
                            'LETO_OBNOV': 'obnova_streha', 'LETO_OBNO0': 'obnova_fasada'})
    df = df[['EID_STAVBA', 'key', 'obcina', 'cat', 'm2', 'year', 'obnova_streha', 'obnova_fasada', 'n_stan']]

    # Deli stavb: pretežna raba (javne stavbe) ter leti obnove oken in instalacij.
    deli = pd.read_csv(ctx.files['deli_stavb'], dtype={'EID_STAVBA': str},
                       usecols=['EID_STAVBA', 'VRSTA_DEJANSKE_RABE_DEL_ST_ID', 'UPORABNA_POVRSINA', 'LETO_OBNOVE_OKEN', 'LETO_OBNOVE_INSTALACIJ'])
    deli['UPORABNA_POVRSINA'] = deli['UPORABNA_POVRSINA'].fillna(0)
    use = deli.groupby(['EID_STAVBA', 'VRSTA_DEJANSKE_RABE_DEL_ST_ID'])['UPORABNA_POVRSINA'].sum().reset_index()
    use['aux'] = use.VRSTA_DEJANSKE_RABE_DEL_ST_ID.isin(AUX_USES)
    # glavne rabe pred pomožnimi; znotraj njih največja površina
    use = use.sort_values(['aux', 'UPORABNA_POVRSINA'], ascending=[True, False]).drop_duplicates('EID_STAVBA')
    df['raba'] = df.EID_STAVBA.map(use.set_index('EID_STAVBA')['VRSTA_DEJANSKE_RABE_DEL_ST_ID'])
    yrs = deli.groupby('EID_STAVBA')[['LETO_OBNOVE_OKEN', 'LETO_OBNOVE_INSTALACIJ']].max()
    df['obnova_okna'] = df.EID_STAVBA.map(yrs['LETO_OBNOVE_OKEN'])
    df['obnova_instal'] = df.EID_STAVBA.map(yrs['LETO_OBNOVE_INSTALACIJ'])

    df['seg'] = np.where(df.cat == 'HISA', 'hise', np.where(df.cat == 'BLOKI', 'bloki',
                         np.where(df.raba.isin(PUBLIC_USES), 'javne', 'zasebne')))

    # Register izkaznic (stanje na dan): vsaka veljavna izkaznica. Specifična primarna energija se izračuna kot v
    # metodologiji razredov NPS 2050: Σ(dovedeni energent × faktor PE) / kondicionirana površina, s filtri
    # dovedena 10–2000 in primarna 10–1500 kWh/(m²·a). Polje »Primarna energija« v registru ni enotno (del zapisov je letni seštevek).
    ei = pd.read_csv(ctx.files['ei_stanje'], sep='|', dtype=str)
    ei['key'] = _key(ei['Šifra KO'], ei['Številka stavbe'])
    ei['EIEI_ID'] = ei['ID energetske izkaznice'].str.split('-').str[-1]
    num = lambda s: pd.to_numeric(s.str.replace('.', '', regex=False).str.replace(',', '.', regex=False), errors='coerce')
    ei['a'] = num(ei['Kondicionirana površina stavbe'])
    tip = ei['Tip izkaznice'].str.strip()
    df['ei_any'] = df.key.isin(set(ei.key))
    df['ei_merjena'] = df.key.isin(set(ei.loc[tip == 'merjena', 'key']))
    en = pd.read_csv(ctx.files['ei_energenti'], sep='|', dtype=str, usecols=['EIEI_ID', 'ENERGENT_SIFRA', 'KOLICINA_PORABLJENEGA_EN'])
    en['f'] = en.ENERGENT_SIFRA.map(PE_FACTORS)
    en['q'] = num(en.KOLICINA_PORABLJENEGA_EN)
    en = en[en.f.notna() & en.q.notna()]
    en['pq'] = en.q * en.f
    tot = en.groupby('EIEI_ID')[['q', 'pq']].sum()
    calc = ei[tip == 'računska'].join(tot, on='EIEI_ID')
    calc = calc[(calc.a > 0) & calc.q.notna()].copy()
    calc['del_s'] = calc.q / calc.a
    calc['pe'] = calc.pq / calc.a
    calc = calc[calc.del_s.between(10, 2000) & calc.pe.between(10, 1500)]
    calc['pw'] = calc.pe * calc.a
    g = calc.groupby('key')[['pw', 'a']].sum()
    df['ei_pe'] = df.key.map(g.pw / g.a)  # površinsko utežena specifična primarna energija računskih izkaznic stavbe

    # Eko sklad: prvo leto izvedbe posamezne vrste ukrepa (matrika do 2024 + poročilo 2025).
    mu = pd.read_excel(ctx.files['es_matrika'], dtype=str)
    mu['key'] = _key(mu['ID_Stavbe'].str.split('-').str[0], mu['ID_Stavbe'].str.split('-', n=1).str[1])
    es25 = pd.read_excel(ctx.files['es_2025'], sheet_name='Podatki', dtype=str)
    es25['key'] = _key(es25.ID_KO, es25.StevilkaStavbe.fillna(''))
    es25['Leto'] = pd.to_numeric(es25.Leto, errors='coerce')
    for grp, (cols, pat) in ES_GROUPS.items():
        y = mu[cols].apply(pd.to_numeric, errors='coerce').replace(0, np.nan).min(axis=1)
        m = pd.Series(y.values, index=mu.key).dropna().groupby(level=0).min()
        m25 = es25[es25.Parameter.str.contains(pat, regex=True, na=False)].groupby('key').Leto.min()
        both = pd.concat([m, m25]).groupby(level=0).min()
        df[f'es_{grp}'] = df.key.map(both)
    df['es_any'] = df[[f'es_{g}' for g in ES_GROUPS]].notna().any(axis=1)

    df['period'] = period(df.year)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    df.to_pickle(CACHE)
    return df
