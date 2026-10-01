"""Graf 4: ključni cilji in kazalniki NPS 2050 (preglednica v povzetku) kot preglednica in mali grafi."""
import re

import openpyxl

from .context import Context, write_csv, write_json
from .draft import row
from . import enote
from .numbers import all_nums, is_missing, lead, year_in

# id, vzorec prve celice, ali ima mali graf
ROWS = [
    ('koncna_energija', r'^Raba končne energije', True),
    ('primarna_energija', r'^Raba primarne energije v stavbah, scenarij', True),
    ('primarna_energija_fiksni', r'^Raba primarne energije pri nespremenjenih', True),
    ('emisije', r'^Emisije TGP', True),
    ('ove', r'^Delež OVE', True),
    ('stopnja_prenove', r'^Letna stopnja energetske prenove', False),
    ('prenovljena_povrsina', r'^Letno prenovljena površina', False),
    ('trajektorija', r'^Povprečna raba primarne energije stanovanjskega fonda', True),
    ('najslabse_stavbe', r'^Prenovljen delež 43 %', True),
    ('meps', r'^Nestanovanjske stavbe: minimalni', False),
    ('fosilna_goriva', r'^Raba fosilnih goriv', False),
    ('energetska_revscina', r'^Energetsko revna', True),
    ('investicije', r'^Investicijske potrebe', False),
    ('nepokrite_investicije', r'^Nepokrite investicijske', False),
    ('koristi', r'^Nižji stroški energije', False),
]
YEARS = [2030, 2040, 2050]


def _label(s: str) -> str:
    return re.sub(r'\s+\d$', '', s).strip()  # odstrani oznako opombe na koncu (… DU-OVE 1)


def _value(cell: str):
    """Številska vrednost za mali graf ali None. Razpon '≤ 3,8–4,6' → zgornja meja, z zapisom razpona."""
    if is_missing(cell) or '/' in cell:
        return None, None
    try:
        v = lead(cell)
    except ValueError:
        return None, None
    rng = None
    m = re.match(r'\s*[≤≥]?\s*([\d.,]+)\s*–\s*([\d.,]+)', cell)
    if m:
        lo, hi = all_nums(m.group(0))
        rng, v = [lo, hi], hi
    return v, rng


def build(ctx: Context) -> dict:
    t = ctx.draft.table(r'^Ključni cilji in kazalniki NPS 2050')
    ctx.check(t[0][3:6] == ['2030', '2040', '2050'], f'glava preglednice kazalnikov: {t[0]}')
    items = []
    for id_, pat, chart in ROWS:
        r = row(t, pat)
        # Številske vrednosti samo za vrstice z malim grafom; ostale vrstice so v načrtu opisne (npr. »16 % stavb (2030)«).
        val = _value if chart else (lambda _c: (None, None))
        base_v, _ = val(r[2])
        item = {
            'id': id_,
            'label': _label(r[0]),
            'unit': r[1],
            'baseline': {'text': r[2], 'value': base_v, 'year': year_in(r[2])},
            'values': [],
            'chart': chart,
        }
        for y, cell in zip(YEARS, r[3:6]):
            v, rng = val(cell)
            item['values'].append({'year': y, 'text': cell, 'value': v, **({'range': rng} if rng else {})})
        if chart:
            ctx.check(base_v is not None and all(x['value'] is not None for x in item['values']),
                      f'kazalnik {id_} ima številsko izhodišče in vrednosti za mali graf')
        items.append(item)
    ctx.check(len(items) == len(t) - 1, f'vse vrstice preglednice kazalnikov so zajete ({len(items)} od {len(t) - 1})')

    _check_grafikoni(ctx, {i['id']: i for i in items})

    # Energetska revščina: vedno zadnje stanje iz preglednice ciljev, če je novejše od povzetka (odločitev Gašperja 1. 10. 2026).
    c = ctx.draft.table(r'Cilj zmanjšanja deleža energetsko revnih gospodinjstev')
    y13 = int(re.search(r'(\d{4})', c[0][-2]).group(1))
    er = next(i for i in items if i['id'] == 'energetska_revscina')
    if er['baseline']['year'] is None or y13 > er['baseline']['year']:
        v13 = c[0][-1].replace('%', '').strip()
        er['baseline'] = {'text': f'{v13} ({y13})', 'value': lead(v13), 'year': y13}

    # ktoe → TWh (§11.12): vrednosti v enotah načrta ostanejo v »plan« (za izpeljane odstotke) in v CSV.
    for it in items:
        texts = [it['baseline']['text']] + [v['text'] for v in it['values']]
        if it['unit'].strip() == 'ktoe':
            it['plan'] = {'baseline': it['baseline']['value'], 'values': [v['value'] for v in it['values']], 'texts': texts}
            it['unit'], it['dec'] = 'TWh', enote.TWH_DEC
            for p in [it['baseline'], *it['values']]:
                p['text'], p['value'] = enote.text_twh(p['text']), enote.twh(p['value'])
                if 'range' in p:
                    p['range'] = [enote.twh(x) for x in p['range']]
        else:
            for p in [it['baseline'], *it['values']]:
                p['text'] = enote.in_text(p['text'])
    ctx.check(not any('ktoe' in str(i) for i in items), 'kazalniki: brez enote ktoe')

    data = {
        'meta': ctx.meta([f'{ctx.draft.name}: preglednica »Ključni cilji in kazalniki NPS 2050« (povzetek)'],
                         note='Vrednosti so zapisane kot v načrtu (text); value je številka za mali graf, pri razponu zgornja meja.'),
        'years': YEARS,
        'items': items,
    }
    write_json('kazalniki', data)
    write_csv('kazalniki', ['kazalnik', 'enota', 'izhodišče', '2030', '2040', '2050', 'izhodišče [ktoe]', '2030 [ktoe]', '2040 [ktoe]', '2050 [ktoe]'],
              [[i['label'], i['unit'], i['baseline']['text'], *[v['text'] for v in i['values']], *(i['plan']['texts'] if 'plan' in i else [None] * 4)] for i in items])
    return data


def _check_grafikoni(ctx: Context, items: dict):
    """Kontrola s podatkovnimi serijami za slike v načrtu (Grafikoni.xlsx, list PROJ)."""
    ws = openpyxl.load_workbook(ctx.files['grafikoni'], read_only=True, data_only=True)['PROJ']
    # List ima več razdelkov z vrstico »Stavbe skupaj« (tudi stopnje prenove v [%]); upoštevajo se le razdelki z leti 2023–2050.
    sections, years = {}, None
    for r in ws.iter_rows(values_only=True):
        if not r or r[0] is None:
            continue
        if str(r[1]).strip() == 'Enota':
            years = list(r[2:6])
        elif str(r[0]).strip() == 'Stavbe skupaj' and years == [2023, 2030, 2040, 2050]:
            sections[str(r[1]).strip()] = list(r[2:6])

    def proj(unit):
        if unit not in sections:
            raise LookupError(f'Grafikoni.xlsx PROJ: ni vrstice »Stavbe skupaj« {unit} z leti 2023–2050')
        return sections[unit]

    for id_, unit, scale in [('koncna_energija', '[ktoe]', 1), ('emisije', '[kt CO2 ekv]', 1), ('ove', '[%]', 100)]:
        vals = proj(unit)
        ours = [items[id_]['baseline']['value']] + [v['value'] for v in items[id_]['values']]
        for y, a, b in zip([2023, *YEARS], ours, vals):
            ctx.check_close(a, round(b * scale), f'kazalnik {id_} {y} = Grafikoni.xlsx PROJ', tol=1)
