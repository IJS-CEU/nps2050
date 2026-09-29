"""Regenerira vse JSON in CSV v public/data/ iz virov (navodila projekta §5).

    python data/build_all.py

Vrne kodo 1, če katerega vira ni ali če katera kontrola ne uspe; takrat se nič ne zapiše v meta.json.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from npsdata import kazalniki, sankey, scenariji, stavbni_fond, trajektorija, ukrepi, zemljevid  # noqa: E402
from npsdata.context import CheckError, Context, write_json  # noqa: E402

MODULES = [('trajektorija', trajektorija), ('stavbni_fond', stavbni_fond), ('scenariji', scenariji), ('kazalniki', kazalniki), ('sankey', sankey), ('zemljevid', zemljevid), ('ukrepi', ukrepi)]


def main() -> int:
    ctx = Context()
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
    if ctx.warnings:
        print(f'\nOPOZORILA – neskladja v osnutku {ctx.draft.name} (na stran gredo vrednosti iz načrta; sporoči avtorjem):')
        for w in ctx.warnings:
            print(f'  ! {w}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
