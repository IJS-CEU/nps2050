"""Energetska revščina: stanje 2024, cilji 2030–2050 in struktura po tipu gospodinjstva (pogl. 2.4 osnutka)."""
from .context import Context, write_csv, write_json
from .draft import row
from .numbers import all_nums, num


def build(ctx: Context) -> dict:
    k = ctx.draft.table(r'^Ključni cilji in kazalniki NPS 2050')
    r = row(k, r'^Energetsko revna gospodinjstva')
    base = all_nums(r[2])  # '7,3 (2024)'
    t2030 = all_nums(r[3])  # '≤ 3,8–4,6'
    t2040, t2050 = all_nums(r[4])[0], all_nums(r[5])[0]
    ctx.check(base == [7.3, 2024.0], f'energetska revščina 2024 = 7,3 % (prebrano {base})')
    ctx.check(t2030 == [3.8, 4.6] and t2040 == 2.5 and t2050 == 1.5, f'cilji energetske revščine 3,8–4,6 / 2,5 / 1,5 % (prebrano {t2030}, {t2040}, {t2050})')

    c = ctx.draft.table(r'Cilj zmanjšanja deleža energetsko revnih gospodinjstev')
    ctx.check(num(c[0][-1]) == 7.3, 'preglednica ciljev: stanje 2024 = 7,3 %')

    n = ctx.draft.table(r'Ocenjeno število energetsko revnih gospodinjstev in oseb')
    hh = num(row(n, r'^Ocenjeno število energetsko revnih gospodinjstev$')[1])
    persons = num(row(n, r'^Ocenjeno število energetsko revnih oseb$')[1])
    cold = num(row(n, r'^Ocenjeno število gospodinjstev, ki si finančno ne morejo')[1])
    arrears = num(row(n, r'^Ocenjeno število gospodinjstev, ki so zaradi finančne')[1])
    leaks = num(row(n, r'^Ocenjeno število gospodinjstev s težavami')[1])
    ctx.check(hh == 63000 and persons == 110000, f'energetsko revna gospodinjstva 63.000, osebe 110.000 (prebrano {hh}, {persons})')

    ty = ctx.draft.table(r'Delež energetsko revnih gospodinjstev po tipu gospodinjstva')
    types = [{'name': x[0], 'pct': num(x[1])} for x in ty[1:] if x and x[0]]
    ctx.check(len(types) == 8 and max(t['pct'] for t in types) == 14.3, 'delež po tipu gospodinjstva: 8 tipov, največ 14,3 %')

    inv = ctx.draft.table(r'Cilj in kazalniki spremljanja naložb URE in rabe OVE v energetsko revnih')
    target_hh = all_nums(row(inv, r'^Število energetsko revnih gospodinjstev z izvedenimi')[1])[0]
    target_gwh = all_nums(row(inv, r'^Kumulativni prihranek')[1])[0]
    ctx.check(target_hh == 8000 and target_gwh == 573, f'cilj naložb 8.000 gospodinjstev, 573 GWh (prebrano {target_hh}, {target_gwh})')

    data = {
        'meta': ctx.meta(
            [f'{ctx.draft.name}: preglednica »Ključni cilji in kazalniki NPS 2050« (povzetek)',
             f'{ctx.draft.name}: preglednice 13–16 (pogl. 2.4, vir podatkov SURS in Akcijski načrt za zmanjševanje energetske revščine 2023)'],
            note='Delež energetsko revnih gospodinjstev po Uredbi o merilih za opredelitev in ocenjevanje števila energetsko revnih gospodinjstev.'),
        'share': {'years': [2024, 2030, 2040, 2050], 'base': base[0], 'target_2030': t2030, 'target_2040': t2040, 'target_2050': t2050},
        'counts_2024': {'households': hh, 'persons': persons, 'cannot_heat': cold, 'arrears': arrears, 'leaks_damp': leaks},
        'by_type_2024': types,
        'investments_2030': {'households': target_hh, 'cumulative_gwh': target_gwh},
    }
    write_json('revscina', data)
    write_csv('revscina_tip_gospodinjstva', ['Tip gospodinjstva', 'Delež energetsko revnih 2024 [%]'], [[t['name'], t['pct']] for t in types])
    return data
