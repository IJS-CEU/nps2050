"""Dnevni nadzor osnutka NPS 2050: ali je v mapi osnutkov nova različica (višji NPS_vNN) ali spremenjena datoteka trenutne.

Primerja najnovejši osnutek (kot ga izbere cevovod) z osnutkom, iz katerega so podatki na strani (public/data/meta.json),
in zgoščeno vrednost datoteke z zadnjim pregledom (data/raw/nadzor_osnutka.json, lokalno, ni v repozitoriju).
Izhod: 0 = brez sprememb, 10 = nova ali spremenjena različica (zaženi build_all.py), 1 = napaka.
"""
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from npsdata.context import OUT, REPO, Context  # noqa: E402

STATE = REPO / 'data' / 'raw' / 'nadzor_osnutka.json'


def main() -> int:
    ctx = Context()
    p = ctx.draft.path
    h = hashlib.md5(p.read_bytes()).hexdigest()
    site = json.loads((OUT / 'meta.json').read_text(encoding='utf-8'))['draft']
    old = json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {}
    new_version = ctx.draft.name != site
    changed = old.get('file') == p.name and old.get('md5') != h
    STATE.write_text(json.dumps({'file': p.name, 'md5': h, 'checked': datetime.now().isoformat(timespec='seconds')}, indent=1), encoding='utf-8')
    print(f'Najnovejši osnutek: {p.name} ({datetime.fromtimestamp(p.stat().st_mtime):%d. %m. %Y %H:%M}); na strani: {site}')
    if new_version:
        print(f'NOVO: nova različica {ctx.draft.name} (na strani je {site}).')
        return 10
    if changed:
        print(f'NOVO: datoteka {p.name} je bila spremenjena od zadnjega pregleda ({old.get("checked")}).')
        return 10
    print('Brez sprememb.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        print(f'NAPAKA: {e}', file=sys.stderr)
        sys.exit(1)
