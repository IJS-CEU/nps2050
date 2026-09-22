"""Graf 1: trajektorija primarne energije stanovanjskega fonda (čl. 9(2) EPBD) in primarna raba stavb v ktoe."""
import re

from .context import Context, write_csv, write_json
from .draft import row
from .numbers import all_nums, is_missing, num


def _split(cell: str) -> tuple[str, str]:
    """'≤ 226 / 217' → ('≤ 226', '217'); '269' → ('', '269')."""
    if ' / ' in cell:
        a, b = cell.split(' / ', 1)
        return a.strip(), b.strip()
    return '', cell.strip()


def build(ctx: Context) -> dict:
    t = ctx.draft.table(r'Nacionalna trajektorija prenove stanovanjskega fonda')
    years = [int(re.match(r'\d{4}', h).group()) for h in t[0][1:]]

    pe = row(t, r'^Povprečna PEU fonda \[kWh')
    nps, epbd = [], []
    for y, cell in zip(years, pe[1:]):
        limit, value = _split(cell)
        nps.append(num(value))
        if limit and not is_missing(limit):
            vals = all_nums(limit)  # '≤ 215–210' → [215, 210]
            epbd.append({'year': y, 'max': max(vals), 'min': min(vals)})

    red = row(t, r'^Zmanjšanje glede na 2020 \[%\]: EPBD')
    reduction = [num(_split(c)[1]) for c in red[1:]]

    # Informativno: pri faktorjih, veljavnih v posameznem letu – samo referenčni scenarij DU-OVE (prvi del celice).
    valid = row(t, r'^Povprečna PEU fonda pri faktorjih, veljavnih')
    nps_valid = [num(_split(c)[0] or c) for c in valid[1:]]

    ctx.check(nps[0] == 269 and nps[-1] == 164, f'trajektorija 2020 in 2050 = 269 in 164 kWh/m² (prebrano {nps[0]}, {nps[-1]})')
    for e in epbd:
        i = years.index(e['year'])
        ctx.check(nps[i] <= e['min'], f'trajektorija {e["year"]} ({nps[i]}) ne presega meje EPBD ({e["min"]}–{e["max"]})')

    # Pogled v ktoe: primarna raba vseh stavb (načrt nima stanovanjskega fonda v ktoe pri fiksnih faktorjih).
    p = ctx.draft.table(r'Primarna raba energije v stavbah po scenariju NPS 2050 \(obseg EPBD\), v ktoe, ter specifična')
    kyears = [int(h) for h in p[0][2:]]
    total = [num(c) for c in row(p, r'^Stavbe skupaj$')[2:]]
    total_fixed = [num(c) for c in row(p, r'^Stavbe skupaj pri faktorjih 2025')[2:]]
    residential = [num(c) for c in row(p, r'^Stanovanjski sektor skupaj$')[2:]]

    data = {
        'meta': ctx.meta(
            [f'{ctx.draft.name}: preglednica »Nacionalna trajektorija prenove stanovanjskega fonda« (pogl. 4.7.1)',
             f'{ctx.draft.name}: preglednica »Primarna raba energije v stavbah po scenariju NPS 2050« (pogl. 4.3)'],
            note='kwh_m2: stanovanjski fond, fiksni faktorji primarne energije (PURES 2021). '
                 'ktoe: vse stavbe v obsegu EPBD; total pri faktorjih, veljavnih v posameznem letu (DU-OVE), total_fixed pri faktorjih 2025.'),
        'kwh_m2': {
            'unit': 'kWh/(m²·a)',
            'years': years,
            'nps': nps,
            'reduction_pct': reduction,
            'epbd_max': epbd,
            'nps_valid_factors': nps_valid,
        },
        'ktoe': {
            'unit': 'ktoe',
            'years': kyears,
            'total': total,
            'total_fixed': total_fixed,
            'residential': residential,
        },
    }
    write_json('trajektorija', data)
    write_csv('trajektorija_kwh_m2', ['leto', 'scenarij NPS 2050 [kWh/(m²·a)]', 'najvišja vrednost po EPBD [kWh/(m²·a)]',
                                      'pri veljavnih faktorjih, informativno [kWh/(m²·a)]'],
              [[y, v, next((f"{e['min']}–{e['max']}" if e['min'] != e['max'] else e['max'] for e in epbd if e['year'] == y), None), w]
               for y, v, w in zip(years, nps, nps_valid)])
    write_csv('trajektorija_ktoe', ['leto', 'vse stavbe [ktoe]', 'vse stavbe pri faktorjih 2025 [ktoe]', 'stanovanjske stavbe [ktoe]'],
              list(map(list, zip(kyears, total, total_fixed, residential))))
    return data
