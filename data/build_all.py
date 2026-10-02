"""Regenerira vse JSON in CSV v public/data/ iz virov (navodila projekta §5).

    python data/build_all.py

Vrne kodo 1, če katerega vira ni ali če katera kontrola ne uspe; takrat se nič ne zapiše v meta.json.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from npsdata import kazalniki, model_obcine, paketi, obcine, spremljanje, trajektorija_zgodba, prihranek, revscina, sankey, scenariji, stavbni_fond, trajektorija, ukrepi, zemljevid  # noqa: E402
from npsdata.context import OUT, REPO, CheckError, Context, write_json  # noqa: E402
import hashlib  # noqa: E402
from datetime import date  # noqa: E402

MODULES = [('trajektorija', trajektorija), ('stavbni_fond', stavbni_fond), ('scenariji', scenariji), ('kazalniki', kazalniki), ('trajektorija_zgodba', trajektorija_zgodba), ('sankey', sankey), ('zemljevid', zemljevid), ('ukrepi', ukrepi), ('revscina', revscina), ('prihranek', prihranek), ('obcine', obcine), ('obcine_model', model_obcine), ('spremljanje', spremljanje), ('paketi_prenove', paketi)]


def main() -> int:
    ctx = Context()
    before = _hashes()
    print(f'Osnutek: {ctx.draft.path.name} ({ctx.draft.date:%d. %m. %Y})')
    for name, mod in MODULES:
        n = len(ctx.checks)
        try:
            mod.build(ctx)
        except (CheckError, LookupError, ValueError) as e:
            print(f'NAPAKA v {name}: {e}', file=sys.stderr)
            return 1
        print(f'  {name}.json  ({len(ctx.checks) - n} kontrol)')
    write_json('meta', ctx.meta(sources=[f'{ctx.draft.path.name}'] + [p.name for p in ctx.files.values()]) | {
        'datasets': [m for m, _ in MODULES],
        'checks': len(ctx.checks),
    })
    print(f'Vse kontrole uspešne ({len(ctx.checks)}).')
    _dnevnik(ctx, before)
    if ctx.warnings:
        print(f'\nOPOZORILA – neskladja v osnutku {ctx.draft.name} (na stran gredo vrednosti iz načrta; sporoči avtorjem):')
        for w in ctx.warnings:
            print(f'  ! {w}')
    return 0


def _hashes() -> dict:
    return {p.relative_to(OUT).as_posix(): hashlib.md5(p.read_bytes()).hexdigest() for p in OUT.rglob('*') if p.is_file() and p.suffix in ('.json', '.csv')}


def _dnevnik(ctx: Context, before: dict):
    """Samodejni vnos v dnevnik sprememb (CLAUDE.md §11.9): en vnos na dan, unija spremenjenih datotek tega dne.
    meta.json in časovni žigi se ne štejejo; datoteke občin se združijo v eno vrstico."""
    after = _hashes()
    changed = {k for k in after if before.get(k) != after[k]} - {'meta.json'}
    path = REPO / 'src' / 'content' / 'dnevnik' / f'{date.today():%Y-%m-%d}-cevovod.md'
    old = set()
    if path.exists():
        old = {l[3:-1] for l in path.read_text(encoding='utf-8').splitlines() if l.startswith('- `')}
    items = old | {('obcine/*.json' if k.startswith('obcine/') else k) for k in changed}
    if not items:
        return
    d = ctx.draft.date
    lines = ['---', f"datum: '{date.today():%Y-%m-%d}'", "naslov: 'Osvežitev podatkov'", 'vrsta: samodejni',
             f'osnutek: {ctx.draft.name}', f"osnutek_datum: '{d:%Y-%m-%d}'", '---', '',
             f'Podatki so preračunani iz osnutka z dne {d.day}. {d.month}. {d.year} in registrov; vse kontrole ({len(ctx.checks)}) so uspešne. Spremenjene datoteke podatkov:', '']
    lines += [f'- `{k}`' for k in sorted(items)]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


if __name__ == '__main__':
    sys.exit(main())
