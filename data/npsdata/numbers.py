"""Branje števil v slovenskem zapisu iz preglednic osnutka (1.149,4 · −15 % · 2,06%)."""
import re

MISSING = {'', '–', '-', '—', 'n.p.'}
_NUM = r'[−\-]?\d{1,3}(?:\.\d{3})+(?:,\d+)?|[−\-]?\d+(?:,\d+)?'


def _clean(s: str) -> str:
    return s.replace('−', '-').replace('\xa0', ' ').strip()


def is_missing(s: str) -> bool:
    return _clean(s) in MISSING


def num(s: str) -> float | None:
    """Celica z enim samim številom. Karkoli drugega sproži ValueError (strogo, da napake ne zdrsnejo mimo)."""
    t = _clean(s).replace('%', '').replace(' ', '')
    if t in MISSING:
        return None
    if not re.fullmatch(_NUM, t):
        raise ValueError(f'ni število: {s!r}')
    return _to_float(t)


def lead(s: str) -> float | None:
    """Prvo število v celici, npr. '976 (−15 %)' → 976, '1.149 (2023)' → 1149."""
    t = _clean(s)
    if t in MISSING:
        return None
    m = re.match(r'\s*[≤≥<>]?\s*(' + _NUM + ')', t)
    if not m:
        raise ValueError(f'celica se ne začne s številom: {s!r}')
    return _to_float(m.group(1))


def all_nums(s: str) -> list[float]:
    return [_to_float(x) for x in re.findall(_NUM, _clean(s))]


def year_in(s: str) -> int | None:
    m = re.search(r'\((\d{4})\)', s)
    return int(m.group(1)) if m else None


def _to_float(t: str) -> float:
    # _NUM dopušča piko samo kot ločilo tisočic, decimalno ločilo je vejica.
    t = t.replace('.', '').replace(',', '.')
    v = float(t)
    return int(v) if v.is_integer() else v
