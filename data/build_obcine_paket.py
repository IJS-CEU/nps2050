"""11.2 Občinski podatkovni paket: en ZIP na občino za lokalni energetski koncept (LEK). Zažene se po build_all.py.

    python data/build_obcine_paket.py

Vsebina ZIP: kazalniki.csv (občina, povprečje sosednjih občin, mediana skupine, Slovenija), obcina.json (vsi podatki občine),
slovar_polj.csv, metapodatki.json in BERIME.txt (vir, licenca). Samo agregati po občini; nič na ravni stavbe.
"""
import csv
import io
import json
import statistics
import zipfile
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / 'public' / 'data'
PAKET = OUT / 'paket'

# polje v kazalu občin → (oznaka, enota)
FIELDS = {
    'pop': ('Prebivalci (1. 1. 2026)', 'število'),
    'buildings': ('Stavbe', 'število'),
    'area_k_m2': ('Uporabna površina stavb', 'tisoč m²'),
    'k_fe_mwh_preb': ('Raba končne energije v vseh stavbah na prebivalca (ocena)', 'MWh'),
    'k_res_fe_mwh_preb': ('Raba končne energije v stanovanjskih stavbah na prebivalca (ocena)', 'MWh'),
    'model_fe_kwh_m2': ('Raba končne energije v stanovanjskih stavbah na m² (ocena)', 'kWh/m²'),
    'k_nres_kwh_m2': ('Raba končne energije v nestanovanjskih stavbah na m² (ocena)', 'kWh/m²'),
    'k_tgp_t_preb': ('Emisije TGP iz stavb na prebivalca (ocena)', 't CO₂ ekv.'),
    'k_ove_pct': ('Delež obnovljivih virov v rabi energije v stavbah (ocena)', '%'),
    'w_res_model_pct': ('Stanovanjska površina v skupini 43 % najmanj učinkovitih (ocena)', '%'),
    'w_res_reg_pct': ('Stanovanjska površina z izkaznico v skupini 43 % (registri)', '%'),
    'w_nres_reg_pct': ('Nestanovanjska površina z izkaznico nad pragom 2030 (registri)', '%'),
    'pre1981_res_area_pct': ('Stanovanjska površina, zgrajena pred 1981', '%'),
    'ei_area_res_pct': ('Stanovanjska površina z veljavno energetsko izkaznico', '%'),
    'es_res_any_pct': ('Stanovanjske stavbe z ukrepom Eko sklada', '%'),
    'obnova_res_pct': ('Stanovanjske stavbe z vpisano obnovo strehe, fasade ali oken (vse)', '%'),
    'obnova_res_since2010_pct': ('Stanovanjske stavbe z vpisano obnovo strehe, fasade ali oken leta 2010 ali pozneje', '%'),
    'k_dh_fe_pct': ('Končna energija goriv in daljinske toplote na območjih z gostoto ≥ 250 MWh/ha', '%'),
    'k_dh_pot_pct': ('Potrebna toplota za ogrevanje na območjih z gostoto ≥ 250 MWh/ha (toplotna karta 2020)', '%'),
    'k_do_sistemi': ('Sistemi daljinskega ogrevanja v občini (AERS 2024)', 'število'),
}
LICENCA = ('© 2026 Institut »Jožef Stefan«, Center za energetsko učinkovitost (IJS CEU). Paket je avtorsko delo in intelektualna lastnina IJS CEU. '
           'Uporaba je dovoljena z navedbo vira »IJS CEU, strokovne podlage NPS 2050«, brez predelave in brez komercialne uporabe '
           '(CC BY-NC-ND 4.0, https://creativecommons.org/licenses/by-nc-nd/4.0/deed.sl). Kontakt: ceu@ijs.si.')


def num(v):
    return '' if v is None else (str(v).replace('.', ',') if isinstance(v, float) else v)


def main():
    ix = json.loads((OUT / 'obcine_index.json').read_text(encoding='utf-8'))
    md = json.loads((OUT / 'obcine_model.json').read_text(encoding='utf-8'))
    sk = json.loads((OUT / 'obcine_skupine.json').read_text(encoding='utf-8'))
    meta = json.loads((OUT / 'meta.json').read_text(encoding='utf-8'))
    y, m, d = map(int, meta['draft_date'].split('-'))
    gname = {g['id']: g['name'] for g in sk['groups']}
    rows = {str(r['sifra']): r for r in ix['municipalities']}
    PAKET.mkdir(parents=True, exist_ok=True)
    for old in PAKET.glob('*.zip'):
        old.unlink()
    for s, r in rows.items():
        me = sk['municipalities'][s]
        nb = [rows[str(n)] for n in me['neighbours'] if str(n) in rows]
        grp = [x for x in rows.values() if sk['municipalities'][str(x['sifra'])]['group'] == me['group']]
        avg = lambda xs, k: round(statistics.mean(v), 2) if (v := [x[k] for x in xs if x.get(k) is not None]) else None
        med = lambda xs, k: round(statistics.median(v), 2) if (v := [x[k] for x in xs if x.get(k) is not None]) else None
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=';')
        w.writerow(['polje', 'kazalnik', 'enota', 'občina', 'povprečje sosednjih občin', f'mediana skupine »{gname[me["group"]]}«', 'Slovenija'])
        for k, (lab, unit) in FIELDS.items():
            w.writerow([k, lab, unit, num(r.get(k)), num(avg(nb, k)), num(med(grp, k)), num(ix['si'].get(k))])
        o = json.loads((OUT / 'obcine' / f'{s}.json').read_text(encoding='utf-8'))
        data = {'obcina': {'sifra': int(s), 'ime': r['name'], 'skupina': gname[me['group']], 'sosednje_obcine': [x['name'] for x in nb]},
                'registri': {k: v for k, v in o.items() if k != 'meta'}, 'model': md['municipalities'][s], 'kazalo': r}
        metadata = {'vir': 'IJS CEU, strokovne podlage NPS 2050', 'osnutek_nps_2050': f'{d}. {m}. {y}', 'izdelano': meta['generated'],
                    'viri_podatkov': meta.get('sources', []), 'licenca': LICENCA,
                    'opomba': 'Ocene modela niso meritve. Cilji NPS 2050 so državni cilji, preneseni na občino; niso obveznost občine. '
                              'Podatki distributerjev zemeljskega plina so v pridobivanju (polja so prazna).'}
        slovar = io.StringIO()
        sw = csv.writer(slovar, delimiter=';')
        sw.writerow(['polje', 'pomen', 'enota'])
        for k, (lab, unit) in FIELDS.items():
            sw.writerow([k, lab, unit])
        readme = (f'Podatkovni paket NPS 2050 za lokalni energetski koncept – občina {r["name"]}\n'
                  f'Osnutek NPS 2050 z dne {d}. {m}. {y}; izdelano {meta["generated"]}.\n\n'
                  'kazalniki.csv  – ključni kazalniki občine s primerjavo (sosednje občine, skupina, Slovenija); podpičje, decimalna vejica\n'
                  'obcina.json    – vsi podatki občine (registri, ocena modela, cilji in pot do 2050, omrežja)\n'
                  'slovar_polj.csv – pomen polj\nmetapodatki.json – viri, datum, licenca\n\n' + LICENCA + '\n')
        with zipfile.ZipFile(PAKET / f'obcina-{s}.zip', 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr('kazalniki.csv', '﻿' + buf.getvalue())
            z.writestr('obcina.json', json.dumps(data, ensure_ascii=False, indent=1))
            z.writestr('slovar_polj.csv', '﻿' + slovar.getvalue())
            z.writestr('metapodatki.json', json.dumps(metadata, ensure_ascii=False, indent=1))
            z.writestr('BERIME.txt', readme)
    print(f'{len(rows)} paketov -> {PAKET}')


if __name__ == '__main__':
    main()
