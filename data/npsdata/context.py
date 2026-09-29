"""Poti do virov (data/sources.toml), osnutek in zapis izhodov v public/data/."""
import csv
import json
import os
import tomllib
from datetime import date
from pathlib import Path

from .draft import Draft, latest_draft

DATA_DIR = Path(__file__).resolve().parent.parent
REPO = DATA_DIR.parent
OUT = REPO / 'public' / 'data'
ENV_ROOTS = {'nps': 'NPS_ROOT', 'greenrenov8': 'GREENRENOV8_ROOT'}


class CheckError(Exception):
    pass


class Context:
    def __init__(self):
        path = DATA_DIR / 'sources.toml'
        if not path.exists():
            raise FileNotFoundError('manjka data/sources.toml – kopiraj data/sources.example.toml in vpiši poti do virov')
        cfg = tomllib.loads(path.read_text(encoding='utf-8'))
        self.roots = {k: Path(os.environ.get(ENV_ROOTS.get(k, ''), v)) for k, v in cfg['roots'].items()}
        self.roots = {k: (p if p.is_absolute() else REPO / p) for k, p in self.roots.items()}
        self.files = {k: self.roots[v['root']] / v['path'] for k, v in cfg['files'].items()}
        for k, p in self.files.items():
            if not p.exists():
                raise FileNotFoundError(f'vir {k!r} ne obstaja: {p}')
        self.draft = Draft(latest_draft(self.roots[cfg['draft']['root']], cfg['draft']['pattern']))
        self.checks: list[str] = []
        self.warnings: list[str] = []

    def meta(self, sources: list[str], note: str | None = None) -> dict:
        m = {
            'draft': self.draft.name,
            'draft_date': self.draft.date.isoformat(),
            'generated': date.today().isoformat(),
            'sources': sources,
            'license': 'CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/), vir: IJS CEU, strokovne podlage NPS 2050',
        }
        if note:
            m['note'] = note
        return m

    def check(self, ok: bool, what: str):
        if not ok:
            raise CheckError(what)
        self.checks.append(what)

    def warn_unless(self, ok: bool, what: str):
        """Neskladje v samem osnutku: na stran gredo številke, kot so v načrtu, neskladje pa se javi avtorjem."""
        if ok:
            self.checks.append(what)
        else:
            self.warnings.append(what)

    def check_close(self, a, b, what: str, tol: float = 0.0):
        self.check(a is not None and b is not None and abs(a - b) <= tol, f'{what}: {a} ≈ {b} (±{tol})')


def write_json(name: str, data: dict):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f'{name}.json').write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


def write_csv(name: str, header: list[str], rows: list[list]):
    """CSV za prenos: UTF-8 z BOM, podpičje in decimalna vejica, da se pravilno odpre v slovenskem Excelu."""
    d = OUT / 'csv'
    d.mkdir(parents=True, exist_ok=True)

    def fmt(v):
        if v is None:
            return ''
        if isinstance(v, float):
            return f'{v}'.replace('.', ',')
        return v

    with open(d / f'{name}.csv', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(header)
        w.writerows([[fmt(v) for v in r] for r in rows])
