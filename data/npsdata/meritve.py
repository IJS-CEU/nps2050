"""Izmerjena raba energije po stavbah (NE objavi se): energetsko knjigovodstvo javnega sektorja (leto 2025) in merjene
energetske izkaznice ter priključek na plinovod iz katastra. Uporablja model_obcine.py samo za seštevke po občinah.

Pretvorbe enot so enake kot v analizi energetskega knjigovodstva projekta PUJS (list »Pretvorba«).
"""
import re
import struct
import zipfile

import numpy as np
import pandas as pd

from .context import DATA_DIR, Context
from .stavbe import CARRIER_GROUP, _key

CACHE = DATA_DIR / 'raw' / 'meritve.pkl'

# (vzorec energenta, enota) → kWh na enoto; enote so poenotene na male črke
CONV = [
    (r'zemeljski plin', 'sm3', 10.327), (r'zemeljski plin', 'm3', 10.327), (r'zemeljski plin', 'nm3', 10.327 / 0.9476),
    (r'zemeljski plin', 'kg', 14.39), (r'bioplin', 'sm3', 5.681), (r'bioplin', 'm3', 5.681),
    (r'unp_uparjen', 'sm3', 25.8), (r'unp_uparjen', 'm3', 25.8), (r'unp_kapljevina', 'l', 7.3), (r'^unp$', 'm3', 25.8), (r'^unp$', 'l', 6.915), (r'^unp$', 'kg', 12.81),
    (r'kurilno olje', 'l', 10.0),
    (r'peleti', 'kg', 4.8), (r'peleti', 'm3', 3120), (r'peleti', 'nm3', 2940), (r'sekanci', 'm3', 800), (r'sekanci', 'nm3', 800),
    (r'polena', 'prm', 1700), (r'lesna biomasa', 'kg', 4.333), (r'lesna biomasa', 'prm', 1700),
]
# ime energenta v knjigovodstvu → skupina (kot v preglednici 30 osnutka)
def group(name: str) -> str | None:
    n = name.lower()
    if 'daljinsk' in n:
        return 'dh'
    if n.startswith('elektrika') or 'sončna elektrarna' in n or 'vetrna' in n:
        return 'el' if n.startswith('elektrika') else 'amb'
    if 'toplota okolja' in n or 'sprejemniki' in n or 'geoterm' in n:
        return 'amb'
    if 'plin' in n or 'unp' in n:
        return 'gas'
    if 'olje' in n or 'premog' in n:
        return 'elko'
    if 'biomas' in n or 'peleti' in n or 'sekanci' in n or 'polena' in n:
        return 'bio'
    if 'spte' in n:
        return 'gas'
    return None


def to_kwh(name: str, unit: str, q: float) -> float:
    u = (unit or '').strip().lower()
    if u == 'kwh':
        return q
    n = name.strip().lower()
    for pat, cu, f in CONV:
        if cu == u and re.search(pat, n):
            return q * f
    return np.nan


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False), errors='coerce')


def _plin(ctx: Context) -> pd.Series:
    """Priključek na plinovod po stavbi iz katastra (polje PLIN v izvozu stavb, DBF)."""
    z = zipfile.ZipFile(ctx.files['kataster_stavbe_zip'])
    raw = z.read('KN_SLO_STAVBE_SLO_STAVBE_tocka.dbf')
    n = struct.unpack('<I', raw[4:8])[0]; hl = struct.unpack('<H', raw[8:10])[0]; rl = struct.unpack('<H', raw[10:12])[0]
    fields, off, pos = [], 1, 32
    while raw[pos] != 0x0D:
        name = raw[pos:pos + 11].split(b'\0')[0].decode(); ln = raw[pos + 16]
        fields.append((name, off, ln)); off += ln; pos += 32
    F = {f[0]: f for f in fields}
    arr = np.frombuffer(raw[hl:hl + n * rl], dtype=f'S{rl}')
    get = lambda k: np.char.strip(np.char.decode(np.array([r[F[k][1]:F[k][1] + F[k][2]] for r in arr]), 'latin-1'))
    return pd.Series(get('PLIN'), index=get('EID_STAVBA'))


def build_measured(ctx: Context, df: pd.DataFrame, refresh: bool = False) -> pd.DataFrame:
    if CACHE.exists() and not refresh:
        return pd.read_pickle(CACHE)
    out = pd.DataFrame(index=df.index)

    # Energetsko knjigovodstvo: letna poročila 2025 (neizbrisana), energenti po enoti, razdeljeni na stavbe enote po površini.
    ek = ctx.files['ek_porocanja'].parent
    rep = pd.read_csv(ek / 'EK_porocanja.csv', sep='|', dtype=str)
    rep['od'] = pd.to_datetime(rep.POROCANJE_OD, dayfirst=True, errors='coerce')
    rep = rep[(rep.DELETED == 'N') & (rep.od.dt.year == 2025)].drop_duplicates('EKPE_ID', keep='last')
    en = pd.read_csv(ek / 'EK_porocanja_energenti.csv', sep='|', dtype=str)
    en = en[(en.DELETED == 'N') & en.EKPO_ID.isin(set(rep.EKPO_ID))].copy()
    en['q'] = _num(en.KOLICINA)
    en['kwh'] = [to_kwh(a, b, q) for a, b, q in zip(en.ENERGENT.fillna(''), en.ENOTA.fillna(''), en.q)]
    en['grp'] = en.ENERGENT.fillna('').map(group)
    ctx.check(en.kwh.notna().mean() > 0.97, f'meritve: pretvorjenih {100 * en.kwh.notna().mean():.1f} % zapisov energentov knjigovodstva v kWh')
    en = en.drop(columns=['EKPE_ID']).merge(rep[['EKPO_ID', 'EKPE_ID']], on='EKPO_ID')  # EKPE_ID v datoteki energentov je ID zapisa
    per_unit = en.dropna(subset=['kwh', 'grp']).pivot_table(index='EKPE_ID', columns='grp', values='kwh', aggfunc='sum', fill_value=0)
    st = pd.read_csv(ek / 'EK_porocanja_stavbe.csv', sep='|', dtype=str)
    st = st[st.DELETED == 'N']
    st['key'] = _key(st.SIF_KO, st.STA_SID.str.replace('.', '', regex=False))
    st = st[st.EKPE_ID.isin(per_unit.index)].drop_duplicates(['EKPE_ID', 'key'])
    area = df.set_index('key').m2.groupby(level=0).sum()
    st['m2'] = st.key.map(area)
    st = st[st.m2.notna()]
    st['share'] = st.m2 / st.groupby('EKPE_ID').m2.transform('sum')
    ctx.check(st.EKPE_ID.nunique() / len(per_unit) > 0.85, f'meritve: {st.EKPE_ID.nunique()} od {len(per_unit)} enot knjigovodstva povezanih s katastrom')
    alloc = st[['EKPE_ID', 'key', 'share']].merge(per_unit, left_on='EKPE_ID', right_index=True)
    cols = [c for c in per_unit.columns]
    for c in cols:
        alloc[c] = alloc[c] * alloc.share
    bk = alloc.groupby('key')[cols].sum()
    keys = df.key
    for c in ['el', 'amb', 'gas', 'elko', 'bio', 'dh']:
        out[f'ek_{c}'] = keys.map(bk[c]) if c in bk else np.nan
    out['ek_any'] = keys.isin(bk.index)

    # Merjene izkaznice: dovedena energija po energentih (samo zapisi v kWh), seštevek po stavbi.
    ei = pd.read_csv(ctx.files['ei_stanje'], sep='|', dtype=str)
    ei = ei[ei['Tip izkaznice'].str.strip() == 'merjena']
    ei['key'] = _key(ei['Šifra KO'], ei['Številka stavbe'])
    ei['EIEI_ID'] = ei['ID energetske izkaznice'].str.split('-').str[-1]
    ee = pd.read_csv(ctx.files['ei_energenti'], sep='|', dtype=str, usecols=['EIEI_ID', 'ENERGENT_SIFRA', 'KOLICINA_PORABLJENEGA_EN'])
    ee = ee[ee.EIEI_ID.isin(set(ei.EIEI_ID))].copy()
    ee['grp'] = ee.ENERGENT_SIFRA.map(CARRIER_GROUP)
    ee['q'] = _num(ee.KOLICINA_PORABLJENEGA_EN)
    ee = ee.dropna(subset=['grp', 'q']).merge(ei[['EIEI_ID', 'key']], on='EIEI_ID')
    mk = ee.pivot_table(index='key', columns='grp', values='q', aggfunc='sum', fill_value=0)
    for c in ['el', 'amb', 'gas', 'elko', 'bio', 'dh']:
        out[f'mei_{c}'] = keys.map(mk[c]) if c in mk else np.nan
    out['mei_any'] = keys.isin(mk.index)

    plin = _plin(ctx)
    # šifrant DA_NE: 0 ni podatka, 1 da, 2 ne (večina stavb nima podatka)
    out['plin'] = pd.to_numeric(df.EID_STAVBA.map(plin), errors='coerce').eq(1)
    out.to_pickle(CACHE)
    return out
