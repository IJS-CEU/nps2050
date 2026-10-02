"""11.2 Daljinsko ogrevanje po občinah: sistemi, prodana toplota in viri (AERS, poročila izvajalcev za leto 2024).

Vir: P:/1 IJS/Baze/Daljinsko ogrevanje/AERS_DO_ 2024_Analiza_ĐOM_2025.xlsx, list »Tabela_Obcine_2024«
(ena vrstica na občino; energije v TJ). Občine se povežejo po imenu (brez »Mestna občina« / »Občina«).
Dolžina omrežja v bazi ni podana.
"""
import re

import openpyxl

TJ_GWH = 1 / 3.6


# Imena v bazi AERS, ki se razlikujejo od imen v Registru prostorskih enot
ALIAS = {'šentjur pri celju': 'šentjur', 'kanal ob soči': 'kanal', 'sveti andraž v slovenskih goricah': 'sveti andraž v slov. goricah'}


def _norm(s: str) -> str:
    s = re.sub(r'^(Mestna občina|Občina)\s+', '', str(s).strip())
    s = re.split(r'\s+-\s+\S+ (község|comune|község)', s)[0]  # dvojezična imena (Hodoš - Hodos község)
    s = re.sub(r'\s*-\s*', '-', s).lower()
    return ALIAS.get(s, s)


def build(ctx, muni: dict) -> dict:
    """muni: eid -> (šifra, ime). Vrne šifra -> podatki o daljinskem ogrevanju (prazen slovar, če občina sistema nima)."""
    ws = openpyxl.load_workbook(ctx.files['daljinsko'], read_only=True, data_only=True)['Tabela_Obcine_2024']
    rows = list(ws.iter_rows(values_only=True))
    hdr = rows[5]
    ctx.check(hdr[1] == 'ObcinaNaziv' and hdr[8] == 'Skupaj (brez hladu)' and rows[1][16] == 'DO prodaja' and rows[1][31] == 'OVE',
              'daljinsko ogrevanje: glava lista Tabela_Obcine_2024')
    by_name = {_norm(n): str(s) for s, n in muni.values()}
    by_name.update({_norm(n).split('/')[0]: str(s) for s, n in muni.values()})
    out, miss = {}, []
    for r in rows[6:]:
        if not r[1]:
            continue
        s = by_name.get(_norm(r[1]))
        if s is None:
            miss.append(r[1]); continue
        n = int(r[8] or 0)
        if n == 0 and not (r[16] or 0):
            continue
        out[s] = {
            'sistemi': n,
            'proizvodnja_gwh': round((r[12] or 0) * TJ_GWH, 1),
            'prodaja_gwh': round((r[16] or 0) * TJ_GWH, 1),
            # viri toplote so pripisani občini proizvodnje; pri nakupu toplote iz sosednje občine (npr. Velenje – Šoštanj) niso znani
            'ove_pct': round(100 * r[31], 0) if isinstance(r[31], (int, float)) and (r[12] or 0) > 0 else None,
            'plin_pct': round(100 * r[30], 0) if isinstance(r[30], (int, float)) and (r[12] or 0) > 0 else None,
            'ucinkovit': r[117] == 'Učinkovito' if r[117] in ('Učinkovito', 'Neučinkovito') else None,
            'spte': int(r[9] or 0),
        }
    ctx.check(not miss, f'daljinsko ogrevanje: vse občine povezane po imenu (nepovezane: {miss[:5]})')
    tot = sum(v['prodaja_gwh'] for v in out.values())
    ctx.check(1300 < tot < 2000, f'daljinsko ogrevanje: prodana toplota {tot:.0f} GWh (AERS 2024)')
    return out
