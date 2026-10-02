"""11.1 Regulativni koledar 2026–2050: datumi, ki zadevajo stavbe, s ciljno skupino in statusom (veljavno / predlagano).

Vir: preglednica, ki jo je potrdil Gašper 2. 10. 2026 (za-potrditev/11.1_koledar_osnutek.xlsx), sestavljena iz osnutka NPS 2050
(pogl. 3, 4.7, 6, 9) in EPBD 2024/1275. Vrstice z »ne« v stolpcu POTRDITEV se izpustijo; popravek v tem stolpcu nadomesti opis.
"""
import re

import pandas as pd

from .context import Context, write_csv, write_json

KOGA = ['lastniki hiš', 'lastniki stanovanj in upravniki', 'občine in javni sektor', 'podjetja in storitveni sektor',
        'projektanti in izdelovalci izkaznic', 'država']
KOGA_ID = {'lastniki hiš': 'hise', 'lastniki stanovanj in upravniki': 'stanovanja', 'občine in javni sektor': 'obcine',
           'podjetja in storitveni sektor': 'podjetja', 'projektanti in izdelovalci izkaznic': 'stroka', 'država': 'drzava'}
MES = ['januar', 'februar', 'marec', 'april', 'maj', 'junij', 'julij', 'avgust', 'september', 'oktober', 'november', 'december']


def _date(s: str):
    """(oznaka, ključ za razvrščanje, leto ali None)."""
    s = str(s).strip()
    if m := re.fullmatch(r'(\d{4})-(\d{2})-(\d{2})', s):
        y, mo, d = map(int, m.groups())
        return f'{d}. {mo}. {y}', f'{y:04d}-{mo:02d}-{d:02d}', y
    if m := re.fullmatch(r'(\d{4})-(\d{2})', s):
        y, mo = map(int, m.groups())
        return f'{MES[mo - 1]} {y}', f'{y:04d}-{mo:02d}-99', y
    if m := re.match(r'(\d{1,2})\. (\d{1,2})\. (\d{4})', s):
        d, mo, y = map(int, m.groups())
        return s, f'{y:04d}-{mo:02d}-{d:02d}', y
    if m := re.search(r'(\d{4})', s):
        y = int(m.group(1))
        return s.replace('-', '–'), f'{y:04d}-99-99', y
    if re.search(r'(nato )?letno|vsako leto', s):
        return 'vsako leto', '9999', None
    return s, '9998', None


def build(ctx: Context) -> dict:
    x = pd.read_excel(ctx.files['koledar'], sheet_name='koledar', dtype=str).fillna('')
    ctx.check(list(x.columns[:10]) == ['datum', 'datum_negotov', 'naslov', 'opis', 'vrsta', 'status', 'koga_zadeva', 'segment', 'vir', 'povezava'],
              'koledar: glava preglednice')
    pot = x.columns[11]
    items = []
    for i, r in x.iterrows():
        p = str(r[pot]).strip()
        if p.lower() == 'ne':
            continue
        lab, key, y = _date(r.datum)
        koga = [k.strip() for k in r.koga_zadeva.split(',') if k.strip()]
        ctx.check(all(k in KOGA for k in koga), f'koledar: znane ciljne skupine ({r.naslov})')
        ctx.check(r.vrsta in ('obveznost', 'cilj', 'mejnik', 'pregled', 'postopek') and r.status in ('veljavno', 'predlagano'), f'koledar: vrsta in status ({r.naslov})')
        opis = p if p and p.lower() not in ('da', 'ok') else r.opis
        if 'ETS2' in r.naslov:
            opis += ' Začetek je odvisen od odločitve EU (možen zamik na leto 2028).'
        items.append({'id': f'k{i + 1:03d}', 'datum': lab, 'kljuc': key, 'leto': y, 'okvirno': r.datum_negotov == 'da',
                      'naslov': r.naslov, 'opis': opis, 'vrsta': r.vrsta, 'status': r.status,
                      'koga': [KOGA_ID[k] for k in koga], 'segment': r.segment, 'vir': r.vir, 'povezava': r.povezava or None})
    items.sort(key=lambda d: (d['kljuc'], d['naslov']))
    ctx.check(len(items) >= 50, f'koledar: {len(items)} vnosov')
    data = {
        'meta': ctx.meta(['Osnutek NPS 2050 (pogl. 3, 4.7, 6, 9) in Direktiva (EU) 2024/1275 (EPBD); preglednico potrdil IJS CEU / MzIE'],
                         note='Status »veljavno«: že v zakonu ali predpisu oziroma v veljavni uredbi ali direktivi EU z rokom, ki ne potrebuje prenosa. '
                              '»Predlagano«: predlaga NPS 2050 ali EPBD, še ni preneseno v slovenske predpise.'),
        'skupine': [{'id': KOGA_ID[k], 'ime': k} for k in KOGA],
        'vnosi': items,
    }
    write_json('koledar', data)
    write_csv('koledar', ['datum', 'okvirno', 'naslov', 'opis', 'vrsta', 'status', 'koga zadeva', 'segment', 'vir'],
              [[d['datum'], 'da' if d['okvirno'] else '', d['naslov'], d['opis'], d['vrsta'], d['status'],
                ', '.join(k for k in KOGA if KOGA_ID[k] in d['koga']), d['segment'], d['vir']] for d in items])
    return data
