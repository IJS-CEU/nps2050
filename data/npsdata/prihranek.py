"""Okvirni prihranek celovite prenove do razreda B1 po izhodiščnem razredu toplotnih potreb (pogl. 4.1.1, model RenRates)."""
from .context import Context, write_csv, write_json
from .numbers import num


def build(ctx: Context) -> dict:
    t = ctx.draft.table(r'Specifična raba končne energije po razredih toplotnih potreb in prihranek celovite')
    rows = []
    for r in t[1:]:
        if not r or not r[0].strip():
            continue
        rows.append({
            'class': r[0].strip(),
            'area_mio_m2': num(r[1]),
            'sfh_use': num(r[2]), 'sfh_saving': num(r[3]),
            'mfh_use': num(r[4]), 'mfh_saving': num(r[5]),
            'per_euro_vs_c': r[6].strip(),
        })
    ctx.check([x['class'] for x in rows] == ['G', 'F', 'E', 'D', 'C'], f'prihranek: razredi G–C (prebrano {[x["class"] for x in rows]})')
    for x in rows:
        # Raba po prenovi (raven B1) je za vse izhodiščne razrede enaka.
        ctx.check(x['sfh_use'] - x['sfh_saving'] == rows[0]['sfh_use'] - rows[0]['sfh_saving'], f'prihranek {x["class"]}: enaka raba po prenovi (enodružinske)')
        ctx.check(x['mfh_use'] - x['mfh_saving'] == rows[0]['mfh_use'] - rows[0]['mfh_saving'], f'prihranek {x["class"]}: enaka raba po prenovi (večstanovanjske)')
    data = {
        'meta': ctx.meta(
            [f'{ctx.draft.name}: preglednica »Specifična raba končne energije po razredih toplotnih potreb in prihranek celovite energetske prenove na raven razreda B1« (pogl. 4.1.1)'],
            note='Model RenRates, povprečje arhetipov. Razredi so razredi toplotnih potreb, raba je končna energija v kWh/(m²·a).'),
        'after': {'sfh': rows[0]['sfh_use'] - rows[0]['sfh_saving'], 'mfh': rows[0]['mfh_use'] - rows[0]['mfh_saving']},
        'rows': rows,
    }
    write_json('prihranek', data)
    write_csv('prihranek_prenova_B1', ['Izhodiščni razred', 'Površina 2025 [mio m²]', 'Enodružinske: raba [kWh/(m²·a)]', 'Enodružinske: prihranek do B1 [kWh/(m²·a)]',
                                       'Večstanovanjske: raba [kWh/(m²·a)]', 'Večstanovanjske: prihranek do B1 [kWh/(m²·a)]', 'Prihranek na evro spodbude glede na razred C'],
              [[x['class'], x['area_mio_m2'], x['sfh_use'], x['sfh_saving'], x['mfh_use'], x['mfh_saving'], x['per_euro_vs_c']] for x in rows])
    return data
