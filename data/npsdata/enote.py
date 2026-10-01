"""Pretvorba ktoe → TWh / GWh (CLAUDE.md §11.12). Pretvorba se naredi samo tu, v cevovodu; komponente prikažejo, kar dobijo.

1 ktoe = 11,63 GWh = 0,01163 TWh (IEA; isti faktor uporablja načrt pri kWh/m²). TWh na dve decimalki, GWh na celo število.
Načrt sam ostaja v ktoe (tako poroča Evropski komisiji); polja v ktoe ostanejo v izvozih CSV za primerljivost.
"""
import re

from .numbers import _NUM, _to_float

KTOE_GWH = 11.63
TWH_DEC = 2


def twh(v: float | None) -> float | None:
    return None if v is None else round(v * KTOE_GWH / 1000, TWH_DEC)


def gwh(v: float | None) -> int | None:
    return None if v is None else int(round(v * KTOE_GWH))


def fmt(v: float, dec: int) -> str:
    """Slovenski zapis: decimalna vejica, pika za tisočice."""
    s = f'{abs(v):,.{dec}f}'.replace(',', ' ').replace('.', ',').replace(' ', '.')
    return ('−' if v < 0 else '') + s


def text_twh(text: str) -> str:
    """Besedilo vrednosti iz načrta v ktoe (npr. »1.149 (2023)«, »976 (−15 %)«): številke pred oklepajem → TWh."""
    head, sep, tail = text.partition('(')
    head = re.sub(_NUM, lambda m: fmt(twh(_to_float(m.group(0))), TWH_DEC), head)
    return head + sep + tail


def in_text(text: str) -> str:
    """Navedbe »N ktoe« ali »N–M ktoe« v besedilu → GWh (pod 1 TWh) ali TWh."""
    def rep(m):
        nums = [_to_float(m.group(1))] + ([_to_float(m.group(2))] if m.group(2) else [])
        if max(nums) * KTOE_GWH >= 1000:
            out = '–'.join(fmt(twh(x), TWH_DEC) for x in nums) + ' TWh'
        else:
            out = '–'.join(fmt(gwh(x), 0) for x in nums) + ' GWh'
        return out
    return re.sub(rf'({_NUM})(?:\s*[–-]\s*({_NUM}))?\s*ktoe', rep, text)


def deep(obj):
    """in_text na vseh nizih v strukturi (za opisna besedila iz načrta)."""
    if isinstance(obj, str):
        return in_text(obj)
    if isinstance(obj, list):
        return [deep(x) for x in obj]
    if isinstance(obj, dict):
        return {k: deep(v) for k, v in obj.items()}
    return obj
