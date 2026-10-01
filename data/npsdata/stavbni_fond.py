"""Graf 2: stavbni fond po segmentih in kategorijah EPBD, s podrobnostmi in cilji za vsako kategorijo."""
import openpyxl

from .context import Context, write_csv, write_json
from .draft import row
from .numbers import num

MIN_CELL = 1  # brez skrivanja majhnih celic: kataster in register izkaznic sta javna (odločitev 29. 9. 2026)
# Najmanjše število izkaznic za prikaz deleža med stavbami z izkaznico (statistična zanesljivost, ne zasebnost).
MIN_EI = 1  # izkaznice so javne: deleži in razredi se prikažejo že pri eni izkaznici, s številom izkaznic (odločitev 1. 10. 2026)

# id (kot v katastru), ime na strani, segment, vzorec prve celice v preglednicah osnutka
CATS = [
    ('HISA', 'Enostanovanjske hiše', 'stanovanjske', r'^Enostanovanjsk'),
    ('BLOKI', 'Večstanovanjske stavbe', 'stanovanjske', r'^Večstanovanjsk'),
    ('PISARNE', 'Pisarne', 'nestanovanjske', r'^Pisarne'),
    ('IZOBRAZ', 'Izobraževanje', 'nestanovanjske', r'^Izobraževanje'),
    ('BOLNICA', 'Zdravstvo', 'nestanovanjske', r'^(Zdravstvo|Bolnišnice)'),
    ('HOTELI', 'Hoteli in gostinstvo', 'nestanovanjske', r'^Hoteli'),
    ('PRODAJA', 'Trgovine', 'nestanovanjske', r'^Trgovine'),
    ('SPORT', 'Šport', 'nestanovanjske', r'^Šport'),
    ('DRUGO', 'Drugo', 'nestanovanjske', r'^Drugo'),
]
CLASS_BOUNDS = ['A|B', 'B|C', 'C|D', 'D|E', 'E|F', 'F|G']


def _suppress(v):
    return None if v is not None and 0 < v < MIN_CELL else v


def build(ctx: Context) -> dict:
    d = ctx.draft
    t3 = d.table(r'Stavbni fond po segmentih NPS 2050 in kategorijah EPBD')
    t_n = d.table(r'Število stavb po kategorijah EPBD in obdobju gradnje')
    t_a = d.table(r'Uporabna površina stavb po kategorijah EPBD in obdobju gradnje')
    t_cls = d.table(r'Meje energijskih razredov (?:2025 )?po kategorijah stavb')
    t_wpb = d.table(r'Pragovi 43 % energijsko najmanj učinkovitih')
    t_meps = d.table(r'Pragovi minimalnih energetskih standardov po kategorijah')
    t_cov = d.table(r'Obseg nestanovanjskih stavb, zajetih z minimalnimi standardi')

    periods = t_n[0][1:-1]
    ctx.check(periods == t_a[0][1:-1], 'obdobja gradnje se ujemajo v preglednicah števila in površine')
    xlsx = _kataster_xlsx(ctx)

    cats = []
    for id_, name, segment, pat in CATS:
        r3 = row(t3, pat)
        rn, ra = row(t_n, pat), row(t_a, pat)
        n_per = [num(c) for c in rn[1:-1]]
        a_per = [num(c) for c in ra[1:-1]]
        ctx.check(sum(n_per) == num(rn[-1]), f'{id_}: vsota stavb po obdobjih = skupaj')
        ctx.check(num(rn[-1]) == num(r3[1]), f'{id_}: število stavb po obdobjih = preglednica 3 ({num(r3[1])})')
        ctx.check_close(num(ra[-1]), num(r3[3]), f'{id_}: površina po obdobjih = preglednica 3', tol=0.05)
        ctx.check(n_per == xlsx['n'][id_], f'{id_}: število stavb po obdobjih = Kataster_fond_po_obdobju_2026.xlsx')
        ctx.check(all(abs(a - b) <= 0.006 for a, b in zip(a_per, xlsx['a'][id_])), f'{id_}: površina po obdobjih = xlsx (±0,006)')

        rc = row(t_cls, pat)
        cat = {
            'id': id_,
            'name': name,
            'segment': segment,
            'buildings': num(r3[1]),
            'area_mio_m2': num(ra[-1]),
            'public_buildings': num(r3[2]),
            'public_area_mio_m2': num(r3[4]),
            # Ogrevana površina v scenariju je v preglednici podana samo za stanovanjske kategorije.
            'heated_area_2020_mio_m2': num(r3[5]),
            'by_period': {'buildings': [_suppress(v) for v in n_per], 'area_mio_m2': a_per},
            'class_bounds': dict(zip(CLASS_BOUNDS, [num(c) for c in rc[1:7]])),
        }
        if segment == 'stanovanjske':
            rw = row(t_wpb, pat)
            cat['worst_43'] = {'threshold': num(rw[2]), 'area_share_pct': num(rw[5]), 'avg_pe_above': num(rw[6])}
        else:
            rm, rv = row(t_meps, pat), row(t_cov, pat)
            cat['meps'] = {
                'threshold_2030': num(rm[2]),
                'threshold_2033': num(rm[3]),
                'indicative': rm[0].rstrip().endswith('*'),
                'covered_2030': {'buildings': num(rv[3]), 'area_mio_m2': num(rv[4])},
                'covered_2033': {'buildings': num(rv[5]), 'area_mio_m2': num(rv[6])},
                'stock_to_2020': {'buildings': num(rv[1]), 'area_mio_m2': num(rv[2])},
            }
        cats.append(cat)

    seg = {}
    for key, pat in [('stanovanjske', r'^Stanovanjske stavbe skupaj'), ('nestanovanjske', r'^Nestanovanjske stavbe skupaj'),
                     ('javne', r'^od tega javne stavbe'), ('zasebne_storitvene', r'^od tega stavbe zasebnega'),
                     ('skupaj', r'^Stavbni fond skupaj')]:
        r = row(t3, pat)
        seg[key] = {'buildings': num(r[1]), 'area_mio_m2': num(r[3]), 'heated_area_2020_mio_m2': num(r[5])}
    for key in ('stanovanjske', 'nestanovanjske'):
        ctx.check(sum(c['buildings'] for c in cats if c['segment'] == key) == seg[key]['buildings'], f'vsota kategorij = {key} skupaj')
    j, z, n = seg['javne']['buildings'], seg['zasebne_storitvene']['buildings'], seg['nestanovanjske']['buildings']
    ctx.warn_unless(j + z == n, f'preglednica 3: javne ({j}) + zasebne storitvene ({z}) = {j + z}, nestanovanjske skupaj = {n}')
    ctx.check(sum(c['public_buildings'] or 0 for c in cats) == seg['javne']['buildings'], 'vsota javnih po kategorijah = javne skupaj')

    data = {
        'meta': ctx.meta(
            [f'{ctx.draft.name}: preglednice »Stavbni fond po segmentih NPS 2050 in kategorijah EPBD«, »Število stavb …«, '
             '»Uporabna površina stavb … po obdobju gradnje« (pogl. 2.1, 2.2.5), »Meje energijskih razredov 2025« (pogl. 3), '
             '»Pragovi 43 % …« (4.7.1), »Pragovi minimalnih energetskih standardov …« in »Obseg nestanovanjskih stavb …« (4.7.2)',
             'Kontrola: Kataster_fond_po_obdobju_2026.xlsx (kataster nepremičnin GURS)'],
            note='Javne stavbe so določene po pretežni dejanski rabi, ne po lastništvu. Uporabna površina po katastru vključuje '
                 'tudi neogrevane površine; ogrevana površina v scenariju NPS 2050 je manjša. Pragovi v kWh/(m²·a) primarne energije. '
                 ''),
        'periods': periods,
        'segments': seg,
        'categories': cats,
    }
    write_json('stavbni_fond', data)
    write_csv('stavbni_fond', ['kategorija', 'segment', 'število stavb', 'od tega javne', 'uporabna površina [mio m²]',
                               'od tega javne [mio m²]'],
              [[c['name'], c['segment'], c['buildings'], c['public_buildings'], c['area_mio_m2'], c['public_area_mio_m2']] for c in cats])
    write_csv('stavbni_fond_po_obdobju', ['kategorija', 'obdobje gradnje', 'število stavb', 'uporabna površina [mio m²]'],
              [[c['name'], p, n, a] for c in cats for p, n, a in zip(periods, c['by_period']['buildings'], c['by_period']['area_mio_m2'])])
    return data


def _kataster_xlsx(ctx: Context) -> dict:
    wb = openpyxl.load_workbook(ctx.files['kataster_obdobje'], read_only=True, data_only=True)
    out = {}
    for key, sheet in [('n', 'Stevilo_stavb'), ('a', 'Uporabna_povrsina_mio_m2')]:
        rows = list(wb[sheet].iter_rows(values_only=True))
        out[key] = {r[0]: [v for v in r[1:9]] for r in rows[1:] if r[0]}
    return out
