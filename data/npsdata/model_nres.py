"""Modelska ocena rabe energije nestanovanjskih stavb (javne in zasebne storitvene) po stavbah; samo za seštevke po občinah.

1. Arhetip RenRates po kategoriji EPBD in obdobju gradnje (pisarne, trgovine, izobraževanje, zdravstvo, kultura in šport,
   hoteli in gostinstvo, novejše stavbe).
2. Računski prostor: osnovna razporeditev arhetipa, računske izkaznice kot močan dokaz, uskladitev po arhetipih;
   prenos v prostor dejanske porabe z operatorjem λ za storitve (1_Calib).
3. Izmerjena raba ima prednost: energetsko knjigovodstvo 2025, sicer merjena izkaznica (le 20–800 kWh/m²).
   Pri elektriki se upošteva 80 % (raba za naprave, IT in kuhanje ni v obsegu EPBD).
4. Modelirane stavbe se po segmentu uskladijo z osnutkom (javne, zasebne storitvene; izhodišče 2023),
   energenti s preglednico 30 (storitve). Daljinska toplota le v občinah, kjer jo potrjujejo izkaznice.
"""
import numpy as np
import pandas as pd

from .draft import row
from .numbers import num
from .stavbe import CARRIERS, HEAT_CLASSES

HC = HEAT_CLASSES
KWH_PER_KTOE = 11.63e6
EL_SCOPE = 0.8
VALID = (20, 800)
EI_WEIGHT = 0.85


def archetype_nres(cat: pd.Series, year: pd.Series) -> np.ndarray:
    y = year.fillna(1970).to_numpy()
    c = cat.to_numpy()
    out = np.full(len(c), 25)
    new = y > 2008
    sel = lambda k: c == k
    out[sel('PISARNE')] = np.select([y[sel('PISARNE')] <= 1965, y[sel('PISARNE')] <= 1981], [14, 15], 16)
    out[sel('PRODAJA')] = np.where(y[sel('PRODAJA')] <= 1945, 17, 18)
    out[sel('IZOBRAZ')] = np.select([y[sel('IZOBRAZ')] <= 1920, y[sel('IZOBRAZ')] <= 1965, y[sel('IZOBRAZ')] <= 1981], [19, 20, 21], 22)
    cus = np.isin(c, ['SPORT', 'DRUGO'])
    out[cus] = np.select([y[cus] <= 1965, y[cus] <= 1981], [23, 24], 25)
    out[sel('BOLNICA')] = np.select([y[sel('BOLNICA')] <= 1965, y[sel('BOLNICA')] <= 1981], [26, 27], 28)
    out[sel('HOTELI')] = np.where(y[sel('HOTELI')] <= 1965, 12, 13)
    out[new] = 30
    return out


def _rake(P, w, target, iters=500):
    for _ in range(iters):
        cur = (w[:, None] * P).sum(0)
        k = np.where(cur > 0, np.maximum(target, 1e-9 * target.sum()) / np.maximum(cur, 1e-12), 1.0)
        if np.abs(k - 1).max() < 1e-7:
            break
        P = P * k
        P /= P.sum(1, keepdims=True)
    return P


def run(ctx, df: pd.DataFrame, meas: pd.DataFrame, rr: dict, dh_m: set) -> pd.DataFrame:
    nr = df[df.seg.isin(['javne', 'zasebne'])].copy()
    ms = meas.loc[nr.index]
    arch = archetype_nres(nr.cat, nr.year)
    n = len(nr)
    area_a = pd.Series(nr.m2.to_numpy()).groupby(arch).sum()
    w = nr.m2.to_numpy() * np.array([rr['arch_all'][a]['stock'] / area_a[a] for a in arch])

    # računski prostor
    P = np.stack([rr['arch_all'][a]['base'] for a in arch])
    kc = nr.ei_razred.map({c: i for i, c in enumerate(HC)})
    known = kc.notna().to_numpy()
    P[known] = EI_WEIGHT * np.eye(9)[kc[known].astype(int)] + (1 - EI_WEIGHT) * P[known]
    for a in np.unique(arch):
        m = arch == a
        P[m] = _rake(P[m], w[m], rr['arch_all'][a]['stock'] * rr['arch_all'][a]['base'])
    Pe = P @ rr['T3s']
    fe = rr['fe'][arch]
    FEc = np.einsum('nc,nck->nk', Pe, fe) * w[:, None]
    tot = FEc.sum(1)
    C = np.zeros((n, 6))
    C[:, [0, 2, 3, 4, 5]] = FEc * 0.95
    C[:, 1] = 0.05 * tot
    obc = nr.obcina.to_numpy()
    no_dh = ~np.isin(obc, list(dh_m))
    move = C[no_dh, 5]
    C[no_dh, 2] += move * 0.6; C[no_dh, 3] += move * 0.4; C[no_dh, 5] = 0
    plin = ms.plin.to_numpy()
    C[plin, 2] += C[plin, 3]; C[plin, 3] = 0

    # izmerjena raba
    def meas_block(prefix):
        M = ms[[f'{prefix}_{c}' for c in CARRIERS]].fillna(0).to_numpy()
        M[:, 0] *= EL_SCOPE
        inten = M.sum(1) / nr.m2.to_numpy()
        ok = ms[f'{prefix}_any'].to_numpy() & (inten >= VALID[0]) & (inten <= VALID[1])
        return M, ok
    Mek, ok_ek = meas_block('ek')
    Mei, ok_ei = meas_block('mei')
    measured = ok_ek | ok_ei
    C[ok_ei] = Mei[ok_ei]
    C[ok_ek] = Mek[ok_ek]

    # uskladitev modeliranih stavb po segmentu z osnutkom
    t14 = ctx.draft.table(r'Končna in primarna raba energije po segmentih stavb v izhodiščnih letih')
    seg_t = {'javne': num(row(t14, r'^Javne stavbe')[2]) * KWH_PER_KTOE, 'zasebne': num(row(t14, r'^Stavbe zasebnega')[2]) * KWH_PER_KTOE}
    seg = nr.seg.to_numpy()
    factors = {}
    for s_, t in seg_t.items():
        mm = seg == s_
        fixed = C[mm & measured].sum()
        free = C[mm & ~measured].sum()
        k = (t - fixed) / free
        factors[s_] = k
        C[mm & ~measured] *= k
    for s_, k in factors.items():
        ctx.check(0.3 < k < 3, f'model nestanovanjskih: faktor uskladitve modeliranih stavb ({s_}) {k:.2f} v razumnem razponu')
    # energenti modeliranih stavb → preglednica 30 (storitve)
    t30 = ctx.draft.table(r'Struktura končne rabe energije po energentih po scenariju NPS 2050')
    r30 = lambda p: num(row(t30, p)[6])
    tc = np.array([r30(r'^Električna'), r30(r'^Toplota okolice') + r30(r'^Sončna'), r30(r'^Zemeljski plin') + r30(r'^Utekočinjeni') + r30(r'^Bioplin'),
                   r30(r'^Ekstra lahko'), r30(r'^Lesna'), r30(r'^Daljinska')]) * KWH_PER_KTOE
    tc *= C.sum() / tc.sum()
    free = ~measured
    tt = C[free].sum(1)
    tgt = np.maximum(tc - C[measured].sum(0), 1e-6 * tc.sum())
    S = C[free] / np.maximum(tt[:, None], 1e-9)
    S = np.where(S.sum(1, keepdims=True) > 0, S, 1 / 6)
    S = _rake(S, tt, tgt)
    C[free] = S * tt[:, None]
    ctx.check(abs(C.sum() / sum(seg_t.values()) - 1) < 0.005, f'model nestanovanjskih: končna raba {C.sum() / KWH_PER_KTOE:.1f} ktoe ≈ osnutek {sum(seg_t.values()) / KWH_PER_KTOE:.0f}')
    out = pd.DataFrame({'obcina': obc, 'seg': seg, 'm2': nr.m2.to_numpy(), 'measured': measured, 'known': known})
    for i, c in enumerate(CARRIERS):
        out[f'c_{c}'] = C[:, i]
    out['fe'] = C.sum(1)
    return out
