"""Rubrika »Ukrepi in financiranje«: ukrepi NEPN 2024 in novi ukrepi N1–N20 (pogl. 6), časovni načrt opuščanja
kotlov (6.1.6) ter investicijske potrebe in viri financiranja (pogl. 7).

Interne opombe v osnutku (npr. »podatek še ni dostopen«, kdo mora vrednost še pripraviti) se ne objavijo
(navodila projekta §7) – nadomesti jih nevtralno »obseg se še določa«.
"""
import re

from . import enote
from .context import Context, write_csv, write_json
from .draft import row
from .numbers import num

GROUPS = [
    ('nepn', r'Pregled obstoječih ukrepov na področju stavb', 'Ukrepi NEPN 2024'),
    ('nepn_novi', r'Pregled novih ukrepov na področju stavb', 'Ukrepi NEPN 2024'),
    ('nps', r'Novi ukrepi za izpolnitev zahtev EPBD', 'Novi ukrepi NPS 2050'),
]
# Vrsta instrumenta → skupina za filter (ključne besede v stolpcu »Vrsta instrumenta«).
KIND = [
    ('predpis', 'Predpisi', r'predpis|uredb|zakon'),
    ('finance', 'Finančne spodbude in instrumenti', r'finan|ekonom|spodbud|davčn|posojil|javno naročanje'),
    ('svetovanje', 'Svetovanje, obveščanje, usposabljanje', r'informir|ozavešč|informativ|usposablj|svetovan|tehnična podpora'),
    ('organizacija', 'Organizacija, načrtovanje, pilotni projekti', r'organizac|načrtovan|pilot|demonstrac|študij|strokovne podlage|sklop|socialni'),
    ('spremljanje', 'Spremljanje, metodologija, podatki', r'spremljan|poročan|metodolog|informacijsk|razvoj, nadgradnja'),
]
INTERNAL = re.compile(r'podatek še ni dostopen|v pripravi|TO ?DO|dopolniti', re.I)


def _areas(s: str) -> list[str]:
    return [a.strip() for a in re.split(r'[,;/]', s) if a.strip()]


def _kinds(s: str) -> list[str]:
    return [k for k, _, pat in KIND if re.search(pat, s, re.I)]


def _deadline_year(s: str) -> int | None:
    y = re.findall(r'(20\d\d)', s)
    return min(int(x) for x in y) if y else None


def build(ctx: Context) -> dict:
    d = ctx.draft
    t47 = d.table(r'Pregled vsebin, ki naslavljajo NEPN ukrepe')
    areas = {r[1].strip(): {'name': r[0].strip(), 'content': r[2]} for r in t47[1:] if len(r) >= 3 and r[1].strip()}
    ctx.check(len(areas) >= 10, f'področja EPBD: {len(areas)} kratic')

    measures = []
    for key, cap, label in GROUPS:
        t = d.table(cap)
        ctx.check(t[0][0] == 'ID' and len(t[0]) == 9, f'{key}: glava preglednice ukrepov')
        cur, last = None, {}
        for r in t[1:]:
            rid, name, area, kind, resp, act, dl, kpi, target = [x.strip() for x in r]
            if rid:
                cur = {'id': rid, 'group': key, 'group_label': label, 'name': name, 'areas': _areas(area), 'activities': []}
                measures.append(cur)
                last = {'kind': kind, 'resp': resp}
            if cur is None:
                continue
            # Navpično spojene celice so v nadaljevalnih vrsticah prazne: podedujejo vrednost prejšnje aktivnosti.
            kind = kind or last.get('kind', '')
            resp = resp or last.get('resp', '')
            last = {'kind': kind, 'resp': resp}
            if not cur['areas'] and area:
                cur['areas'] = _areas(area)
            if not act and not kpi and not target:
                continue
            if not act and cur['activities']:
                a = cur['activities'][-1]
                a['kpi'] = ' / '.join(x for x in [a['kpi'], kpi] if x)
                a['target'] = ' / '.join(x for x in [a['target'], target] if x)
                continue
            cur['activities'].append({'kind': kind, 'resp': resp, 'text': act, 'deadline': dl, 'kpi': kpi, 'target': target})
        # Neznane kratice področij so napaka v branju.
        for m in measures:
            bad = [a for a in m['areas'] if a not in areas]
            ctx.check(not bad, f'{m["id"]}: znana področja EPBD ({bad})')

    for m in measures:
        acts = m['activities']
        m['kinds'] = sorted({k for a in acts for k in _kinds(a['kind'])}) or ['organizacija']
        m['responsible'] = sorted({x.strip() for a in acts for x in re.split(r'[,/]', a['resp']) if x.strip()})
        years = [y for a in acts if (y := _deadline_year(a['deadline']))]
        m['first_deadline'] = min(years) if years else None
        m['recurring'] = any(re.search(r'letno|vsako leto', a['deadline'], re.I) for a in acts)

    n_nepn = sum(1 for m in measures if m['group'] != 'nps')
    n_nps = sum(1 for m in measures if m['group'] == 'nps')
    ctx.check(n_nepn == 24 and n_nps == 20, f'ukrepi: {n_nepn} NEPN + {n_nps} novih (pričakovano 24 + 20)')
    ctx.check([m['id'] for m in measures if m['group'] == 'nps'] == [f'N{i}' for i in range(1, 21)], 'novi ukrepi N1–N20 po vrsti')

    # Časovni načrt opuščanja kotlov na fosilna goriva (pogl. 6.1.6)
    t53 = d.table(r'Časovni načrt opuščanja kotlov na fosilna goriva v stavbah do leta 2040')
    boilers = [{'when': r[0], 'milestone': r[1], 'basis': r[2], 'effect': r[3]} for r in t53[1:] if r[0].strip()]
    ctx.check(len(boilers) >= 8, f'časovni načrt kotlov: {len(boilers)} mejnikov')

    # Investicijske potrebe po segmentih (pogl. 7.1)
    t55 = d.table(r'Investicijske potrebe, spodbujene naložbe in primanjkljaj po segmentih stavb')
    periods = t55[0][1:]
    segs, cur = {}, None
    for r in t55[1:]:
        lab = r[0].strip()
        if all(not c.strip() for c in r[1:]):
            cur = lab
            segs[cur] = {}
            continue
        key = {'Investicijske potrebe': 'needs', 'Spodbujene naložbe': 'leveraged', '…od tega: nepovratna sredstva': 'grants',
               '…od tega: zasebna sredstva': 'private', 'Primanjkljaj (-)': 'gap'}.get(lab)
        if cur and key:
            segs[cur][key] = [None if c.strip() in ('n.p.', '-', '–', '') else num(c.replace(' ', '')) for c in r[1:]]
    ctx.check(set(segs) >= {'Stavbe javnega sektorja', 'Stavbe zasebnega storitvenega sektorja', 'Stanovanjske stavbe'},
              f'investicije: segmenti {list(segs)}')
    three = ['Stanovanjske stavbe', 'Stavbe javnega sektorja', 'Stavbe zasebnega storitvenega sektorja']
    first5 = sum(sum(segs[s]['needs'][:5]) for s in three)
    total = sum(sum(v for v in segs[s]['needs'] if v) for s in three)
    # Preglednica investicij se mora ujemati s povzetkom osnutka (zneski se berejo iz besedila povzetka, ne vpisujejo).
    import re as _re
    from .draft import _text
    body = ' '.join(_text(p._p) for p in ctx.draft.doc.paragraphs)
    m = _re.search(r'Investicijske potrebe za energetsko prenovo znašajo ([\d,]+)\s*mrd €.*?približno ([\d,]+)\s*mrd € do leta 2050\. Ob obstoječih virih ostaja v obdobju 2026–2030 nepokritih ([\d,]+)\s*mrd €', body, _re.S)
    ctx.check(m is not None, 'investicije: zneski v povzetku osnutka')
    p30, p50, pgap = (float(x.replace(',', '.')) for x in m.groups())
    ctx.check_close(first5 / 1000, p30, f'investicije 2026–2030 = {m.group(1)} mrd € (povzetek)', tol=0.01)
    ctx.check_close(total / 1000, p50, f'investicije 2026–2050 ≈ {m.group(2)} mrd € (povzetek)', tol=0.6)
    gap = -sum(sum(v for v in segs[s]['gap'][:5] if v is not None) for s in three)
    ctx.check_close(gap / 1000, pgap, f'nepokrite potrebe 2026–2030 = {m.group(3)} mrd € (povzetek)', tol=0.01)

    # Viri financiranja 2031–2050 (preglednica 56), brez internih opomb
    t56 = d.table(r'Viri financiranja energetske prenove stavb v obdobju 2031–2050')
    sources = []
    for r in t56[1:]:
        amount = r[3]
        if INTERNAL.search(amount):
            amount = 'obseg se še določa'
        sources.append({'source': r[0], 'period': r[2], 'amount': amount, 'purpose': r[4]})
    ctx.check(all(not INTERNAL.search(' '.join(s.values())) for s in sources), 'viri financiranja brez internih opomb')

    # navedbe v ktoe v besedilih načrta → GWh / TWh (§11.12)
    measures, boilers, sources = enote.deep(measures), enote.deep(boilers), enote.deep(sources)

    data = {
        'meta': ctx.meta([f'{d.name}: pogl. 6 (preglednice »Pregled vsebin …«, »Pregled obstoječih ukrepov …«, »Pregled novih ukrepov …«, '
                          '»Novi ukrepi za izpolnitev zahtev EPBD (N1–N20)«, »Časovni načrt opuščanja kotlov …«), '
                          'pogl. 7 (»Investicijske potrebe …«, »Viri financiranja … 2031–2050«)'],
                         note='Novi ukrepi N1–N20 so v osnutku predlog za odločanje; roki in nosilci se uskladijo ob posodobitvi NEPN. '
                              'Investicije v mio EUR; obdobja od 2031 dalje so petletne vsote.'),
        'areas': areas,
        'kinds': [{'id': k, 'name': n} for k, n, _ in KIND],
        'measures': measures,
        'boilers': boilers,
        'investments': {'periods': periods, 'segments': segs, 'total_2026_2030': round(first5), 'total_2026_2050': round(total), 'gap_2026_2030': round(gap)},
        'sources': sources,
    }
    write_json('ukrepi', data)
    write_csv('ukrepi', ['oznaka', 'skupina', 'ukrep', 'področja EPBD', 'nosilci', 'aktivnost', 'rok', 'kazalnik', 'ciljna vrednost'],
              [[m['id'], m['group_label'], m['name'], ', '.join(m['areas']), a['resp'], a['text'], a['deadline'], a['kpi'], a['target']]
               for m in measures for a in m['activities']])
    write_csv('investicije', ['segment', 'kazalnik', *periods],
              [[s, k, *v] for s, ks in segs.items() for k, v in ks.items()])
    return data
