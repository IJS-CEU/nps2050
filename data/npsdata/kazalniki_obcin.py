"""Kazalniki za primerjavo občin: končna energija, emisije TGP in delež OVE vseh stavb, na prebivalca in na m².

- Emisijski faktorji: RenRates (7_Carriers, 2025); daljinska toplota po občini glede na delež OVE sistema (AGEN-RS 2025).
  Vsota po sektorju (stanovanjski, storitveni) se umeri na osnutek NPS 2050 (emisije 2023).
- Delež OVE: lesna biomasa + toplota okolice in sončna energija + delež OVE v elektriki + delež OVE v daljinski toploti občine.
  Delež OVE v elektriki se po sektorju umeri tako, da se država ujema z osnutkom (stanovanjski 60 %, storitveni 33 %, 2023).
- Prebivalci: SURS, stanje 1. 1. 2026.
"""
import json
import re
import unicodedata

import numpy as np
import pandas as pd

from .draft import row
from .numbers import num

EF = {'el': 0.22, 'amb': 0.0, 'gas': 0.202, 'elko': 0.267, 'bio': 0.02, 'dh': 0.20}  # kg CO2 ekv/kWh
# Delež OVE v glavnem distribucijskem sistemu toplote občine (AGEN-RS, Energetsko učinkoviti distribucijski sistemi 2025, »Dosežen delež« OVE).
DH_OVE = {
    'Ljubljana': 13.6, 'Maribor': 17.9, 'Celje': 38.7, 'Velenje': 2.5, 'Šoštanj': 2.5, 'Jesenice': 13.6, 'Kranj': 0, 'Ravne na Koroškem': 0,
    'Trbovlje': 0, 'Hrastnik': 22.1, 'Zagorje ob Savi': 100, 'Nova Gorica': 8.8, 'Šempeter - Vrtojba': 0, 'Piran': 0.8, 'Koper': 0,
    'Murska Sobota': 0, 'Ptuj': 67.6, 'Slovenj Gradec': 80.2, 'Kočevje': 98.2, 'Kamnik': 0, 'Postojna': 100, 'Idrija': 18.9, 'Litija': 0,
    'Grosuplje': 0, 'Lendava': 79.5, 'Krško': 0, 'Žalec': 0, 'Dravograd': 0, 'Mežica': 0, 'Prevalje': 0, 'Črna na Koroškem': 0, 'Novo mesto': 0,
    'Radlje ob Dravi': 100, 'Vuzenica': 100, 'Bohinj': 100, 'Preddvor': 98.3, 'Železniki': 100, 'Bovec': 100, 'Kobarid': 100,
    'Miren - Kostanjevica': 100, 'Semič': 100, 'Trebnje': 100, 'Metlika': 99.5, 'Črnomelj': 99.8, 'Moravče': 100, 'Ivančna Gorica': 100,
    'Ribnica': 99.2, 'Kidričevo': 94.3, 'Lenart': 99.6, 'Oplotnica': 100, 'Mozirje': 100, 'Slovenske Konjice': 90, 'Gornji Grad': 100,
    'Luče': 100, 'Nazarje': 100, 'Solčava': 100, 'Vransko': 100, 'Kozje': 100, 'Tolmin': 100, 'Ajdovščina': 100, 'Sodražica': 100,
    'Loški Potok': 100, 'Pivka': 100, 'Vojnik': 100, 'Kranjska Gora': 100, 'Hrpelje - Kozina': 100, 'Mirna': 100, 'Zreče': 0, 'Šentilj': 0,
    'Polzela': 0, 'Bled': 0,
}


def _norm(s: str) -> str:
    s = unicodedata.normalize('NFKD', s.lower())
    return re.sub(r'[^a-z]', '', ''.join(ch for ch in s if not unicodedata.combining(ch)))


def build(ctx, res: pd.DataFrame, nres: pd.DataFrame, muni: dict, pop_path) -> dict:
    """res, nres: stavbe z energenti c_* (kWh) in stolpcem obcina (EID). muni: EID → (šifra, ime). Vrne kazalnike po občinah in za Slovenijo."""
    names = {eid: nm for eid, (_, nm) in muni.items()}
    lookup = {_norm(k): v for k, v in DH_OVE.items()}
    s_dh = {eid: lookup[_norm(nm)] / 100 for eid, nm in names.items() if _norm(nm) in lookup}
    ctx.check(len(s_dh) >= len(DH_OVE) - 2, f'kazalniki: delež OVE daljinske toplote pripisan {len(s_dh)} od {len(DH_OVE)} občin iz poročila AGEN-RS')

    t32 = ctx.draft.table(r'Emisije toplogrednih plinov v stavbah v opazovanih letih')
    t33 = ctx.draft.table(r'Obnovljivi viri energije v stavbah v opazovanih letih')
    tgp_t = {'res': num(row(t32, r'^Stanovanjski')[2]) * 1e6, 'nres': num(row(t32, r'^Storitveni')[2]) * 1e6}  # kg
    ove_t = {'res': num(row(t33, r'^Stanovanjski')[2]) / 100, 'nres': num(row(t33, r'^Storitveni')[2]) / 100}

    C = ['el', 'amb', 'gas', 'elko', 'bio', 'dh']
    agg = {k: d.groupby('obcina')[[f'c_{c}' for c in C]].sum().rename(columns=lambda x: x[2:]) for k, d in (('res', res), ('nres', nres))}
    ids = sorted(set(muni))
    for k in agg:
        agg[k] = agg[k].reindex(ids, fill_value=0.0)
    dh_all = agg['res'].dh + agg['nres'].dh
    sdh = pd.Series({e: s_dh.get(e, np.nan) for e in ids})
    s_bar = float((sdh * dh_all).sum() / dh_all[sdh.notna()].sum())
    sdh = sdh.fillna(s_bar)  # občine z daljinsko toploto brez podatka AGEN-RS: državno povprečje
    ef_dh = EF['dh'] * (1 - sdh) / (1 - s_bar)

    res_out = {}
    for k, A in agg.items():
        fe = A.sum(1)
        ren_direct = A.bio + A.amb + A.dh * sdh
        s_el = (ove_t[k] * fe.sum() - ren_direct.sum()) / A.el.sum()
        ctx.check(0 <= s_el <= 1, f'kazalniki: umerjen delež OVE v elektriki ({k}) {100 * s_el:.1f} %')
        ove = ren_direct + A.el * s_el
        tgp_raw = sum(A[c] * EF[c] for c in C if c != 'dh') + A.dh * ef_dh
        kf = tgp_t[k] / tgp_raw.sum()
        ctx.check(0.6 < kf < 1.6, f'kazalniki: umeritev emisij ({k}) faktor {kf:.2f}')
        res_out[k] = {'fe': fe, 'ove': ove, 'tgp': tgp_raw * kf, 's_el': s_el, 'k': kf}

    pop = json.loads(open(pop_path, encoding='utf-8').read())
    P = {int(code): v for code, (_, v) in pop['data'].items() if code != '0'}
    si_pop = pop['data']['0'][1]
    ctx.check(abs(sum(P.values()) - si_pop) < 1, f'kazalniki: prebivalci po občinah = Slovenija ({si_pop})')
    area_n = nres.groupby('obcina').m2.sum().reindex(ids, fill_value=0)
    meas_n = nres[nres.measured].groupby('obcina').m2.sum().reindex(ids, fill_value=0)

    def block(eids, p):
        f = {k: float(res_out[k]['fe'][eids].sum()) for k in res_out}
        o = {k: float(res_out[k]['ove'][eids].sum()) for k in res_out}
        t = {k: float(res_out[k]['tgp'][eids].sum()) for k in res_out}
        fe_tot, an = f['res'] + f['nres'], float(area_n[eids].sum())
        return {
            'pop': int(p),
            'fe_gwh': {'res': round(f['res'] / 1e6, 1), 'nres': round(f['nres'] / 1e6, 1), 'total': round(fe_tot / 1e6, 1)},
            'tgp_kt': {'res': round(t['res'] / 1e6, 2), 'nres': round(t['nres'] / 1e6, 2), 'total': round((t['res'] + t['nres']) / 1e6, 2)},
            'ove_pct': {'res': round(100 * o['res'] / f['res'], 1) if f['res'] else None, 'nres': round(100 * o['nres'] / f['nres'], 1) if f['nres'] else None,
                        'total': round(100 * (o['res'] + o['nres']) / fe_tot, 1) if fe_tot else None},
            'fe_mwh_preb': {'res': round(f['res'] / 1e3 / p, 2), 'total': round(fe_tot / 1e3 / p, 2)},
            'tgp_t_preb': {'res': round(t['res'] / 1e3 / p, 2), 'total': round((t['res'] + t['nres']) / 1e3 / p, 2)},
            'nres_kwh_m2': round(f['nres'] / an) if an else None,
            'nres_measured_area_pct': round(100 * float(meas_n[eids].sum()) / an, 1) if an else None,
            'dh_ove_pct': None,
        }

    out = {}
    for eid in ids:
        sifra, _ = muni[eid]
        b = block([eid], P[sifra])
        b['dh_ove_pct'] = round(100 * s_dh[eid], 1) if eid in s_dh else None
        out[str(sifra)] = b
    si = block(ids, si_pop)
    si['s_el_pct'] = {k: round(100 * v['s_el'], 1) for k, v in res_out.items()}
    si['dh_ove_pct'] = round(100 * s_bar, 1)
    ctx.check(abs(si['tgp_kt']['total'] - (tgp_t['res'] + tgp_t['nres']) / 1e6) < 1, f'kazalniki: emisije vseh stavb {si["tgp_kt"]["total"]} kt = osnutek')
    return {'si': si, 'municipalities': out, 'pop_period': pop.get('polletje')}
