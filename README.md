# NPS 2050 – strokovne podlage (IJS CEU)

Statična spletna stran (Astro), na kateri IJS CEU predstavi strokovne podlage za Nacionalni načrt prenove stavb NPS 2050. Pripravlja jo Center za energetsko učinkovitost Instituta »Jožef Stefan« (IJS CEU). Podatki so objavljeni pod licenco CC BY 4.0.

## Zagon

Potrebuješ Node 24 in Python 3.12 (s `pandas`, `openpyxl`, `python-docx`).

```bash
npm install
npm run dev       # razvojni strežnik, http://localhost:4321/
npm run build     # preverjanje tipov + gradnja v dist/
npm run preview   # ogled zgrajene strani
```

Gradnja za podmapo (npr. GitHub Pages):

```bash
ASTRO_BASE=/nps2050/ ASTRO_SITE=https://ijs-ceu.github.io npm run build
```

V Git Bash na Windows dodaj `MSYS_NO_PATHCONV=1`, sicer Git Bash `/nps2050/` pretvori v Windows pot.

## Osvežitev podatkov

Grafi berejo samo JSON v `public/data/`. Ustvari jih cevovod iz izvornih datotek (osnutek načrta, kataster, model). Poti do njih so v `data/sources.toml`, ki ni v repozitoriju: kopiraj `data/sources.example.toml` in vpiši svoje poti.

```bash
python -m pip install --user -r data/requirements.txt
npm run data          # = python data/build_all.py
```

- Osnutek je vedno najvišji `NPS_vNN.docx` v mapi NPS; nova različica se pobere samodejno.
- Cevovod izvede kontrole (vsote, osnutek proti xlsx). Če katera ne uspe, se ustavi z opisom napake in ne prepiše podatkov. Neskladja v samem osnutku izpiše kot »OPOZORILA« – te sporoči avtorjem načrta.
- Namesto urejanja `sources.toml` lahko nastaviš okoljski spremenljivki `NPS_ROOT` in `GREENRENOV8_ROOT`.

Surovi podatki se ne kopirajo v repozitorij (`data/raw/` je v `.gitignore`). Po osvežitvi commitaj spremenjene datoteke v `public/data/`.

## Preverjanje

V enem terminalu `npm run build && npm run preview`, v drugem:

```bash
npm run test:a11y   # dostopnost (axe, WCAG 2.1 AA): vseh 7 strani, svetla/temna tema, 400/1280 px
npm run test:snap   # posnetki in kontrola praznih grafov
```

`test:a11y` konča z napako, če najde kršitev stopnje »critical« ali »serious«. `tests/snap.mjs` posname naslovno stran in Strokovne podlage v svetli in temni temi pri 400 in 1280 px (v `screenshots/`, ni v gitu) in javi vodoravno drsenje, prazne grafe ali napake v konzoli. Prvič je treba namestiti brskalnik: `npx playwright install chromium`.

## Besedila

Stran je samo v slovenščini.

- Vsaka rubrika je ena datoteka MDX: `src/content/pages/<id>.mdx`. Besedilo urediš neposredno v njej; ob vsak podatek dodaj komentar `{/* vir: NPS_vNN, pogl. … */}`.
- Seznam rubrik in poti je v `src/i18n/routes.ts`, oznake navigacije in vmesnika v `src/i18n/ui.ts`.

## Struktura

```
src/content/pages/           besedila rubrik (MDX)
src/i18n/                    poti in nizi vmesnika
src/layouts, src/components  postavitev, glava, noga, grafi
src/styles/                  žetoni barv (svetla/temna tema)
public/data/                 JSON iz cevovoda
public/logos/                uporabljeni logotipi (izvirniki v design/logos/)
data/                        podatkovni cevovod (Python)
```
