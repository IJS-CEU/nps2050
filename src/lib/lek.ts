/**
 * Izvoz za lokalni energetski koncept (LEK): skupni podatki za izvleček za tisk in CSV.
 * Izvoz je podpisan kot intelektualna lastnina IJS CEU (odločitev Gašperja, 29. 9. 2026).
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { loadData, type Obcina, type ObcineIndex, type ObcineModel } from './data';

export const LEK_SIGN = '© 2026 Institut »Jožef Stefan«, Center za energetsko učinkovitost (IJS CEU). Izvleček je avtorsko delo in intelektualna lastnina IJS CEU. '
  + 'Uporaba je dovoljena z navedbo vira »IJS CEU, strokovne podlage NPS 2050«, brez predelave in brez komercialne uporabe '
  + '(CC BY-NC-ND 4.0, https://creativecommons.org/licenses/by-nc-nd/4.0/deed.sl). Kontakt: ceu@ijs.si.';

export function lekData(sifra: string) {
  const ix = loadData<ObcineIndex>('obcine_index');
  const md = loadData<ObcineModel>('obcine_model');
  const o = JSON.parse(readFileSync(resolve(process.cwd(), 'public', 'data', 'obcine', `${sifra}.json`), 'utf-8')) as Obcina;
  const meta = loadData<{ draft_date: string; draft: string }>('meta');
  const [y, m, d] = meta.draft_date.split('-').map(Number);
  return { ix, md, o, mo: md.municipalities[sifra], ms: md.si, si: ix.si, draftDate: `${d}. ${m}. ${y}`, draft: meta.draft };
}

/** Vrstice kazalnik – enota – občina – Slovenija (za CSV in preglednico). */
export function lekRows(sifra: string): [string, string, string | number | null, string | number | null][] {
  const { o, mo, ms, si, ix } = lekData(sifra);
  const row = ix.municipalities.find((r) => String(r.sifra) === sifra);
  const va = mo.vse, vs = ms.vse, ci = mo.cilji!;
  const seg = (k: string) => o.segments[k];
  return [
    ['Prebivalci (1. 1. 2026)', 'število', va.pop, vs.pop],
    ['Stavbe', 'število', o.buildings, si.buildings],
    ['Uporabna površina stavb', 'tisoč m²', o.area_k_m2, si.area_k_m2],
    ['Enostanovanjske hiše', 'število', seg('hise').buildings, si.segments.hise.buildings],
    ['Večstanovanjske stavbe', 'število', seg('bloki').buildings, si.segments.bloki.buildings],
    ['Javne stavbe', 'število', seg('javne').buildings, si.segments.javne.buildings],
    ['Stavbe zasebnega storitvenega sektorja', 'število', seg('zasebne').buildings, si.segments.zasebne.buildings],
    ['Stanovanjska površina, zgrajena pred 1981', '%', row?.pre1981_res_area_pct ?? null, si.pre1981_res_area_pct],
    ['Stanovanjska površina z veljavno energetsko izkaznico', '%', row?.ei_area_res_pct ?? null, si.ei_area_res_pct],
    ['Stanovanjske stavbe z ukrepom Eko sklada', '%', o.es_res_any_pct, si.es_res_any_pct],
    ['Raba končne energije v vseh stavbah (ocena)', 'GWh/leto', va.fe_gwh.total, vs.fe_gwh.total],
    ['– od tega stanovanjske stavbe', 'GWh/leto', va.fe_gwh.res, vs.fe_gwh.res],
    ['– od tega nestanovanjske stavbe', 'GWh/leto', va.fe_gwh.nres, vs.fe_gwh.nres],
    ['Raba končne energije v stavbah na prebivalca', 'MWh', va.fe_mwh_preb.total, vs.fe_mwh_preb.total],
    ['Raba končne energije v stanovanjskih stavbah na prebivalca', 'MWh', va.fe_mwh_preb.res, vs.fe_mwh_preb.res],
    ['Raba končne energije v stanovanjskih stavbah na m²', 'kWh/m²', mo.fe_kwh_m2, ms.fe_kwh_m2],
    ['Raba končne energije v nestanovanjskih stavbah na m²', 'kWh/m²', va.nres_kwh_m2, vs.nres_kwh_m2],
    ['Emisije TGP iz stavb', 'kt CO₂ ekv./leto', va.tgp_kt.total, vs.tgp_kt.total],
    ['Emisije TGP iz stavb na prebivalca', 't CO₂ ekv.', va.tgp_t_preb.total, vs.tgp_t_preb.total],
    ['Delež obnovljivih virov v rabi energije v stavbah', '%', va.ove_pct.total, vs.ove_pct.total],
    ['Stanovanjske stavbe: električna energija', '% končne energije', mo.carriers_pct.el, ms.carriers_pct.el],
    ['Stanovanjske stavbe: toplota okolice in sončna energija', '% končne energije', mo.carriers_pct.amb, ms.carriers_pct.amb],
    ['Stanovanjske stavbe: plin', '% končne energije', mo.carriers_pct.gas, ms.carriers_pct.gas],
    ['Stanovanjske stavbe: kurilno olje', '% končne energije', mo.carriers_pct.elko, ms.carriers_pct.elko],
    ['Stanovanjske stavbe: lesna biomasa', '% končne energije', mo.carriers_pct.bio, ms.carriers_pct.bio],
    ['Stanovanjske stavbe: daljinska toplota', '% končne energije', mo.carriers_pct.dh, ms.carriers_pct.dh],
    ['Stanovanjska površina nad pragom 43 % najmanj učinkovitih (ocena)', '%', mo.above43_area_pct, ms.above43_area_pct],
    ['NPS 2050: potrebna energetska prenova 2026–2030', 'm²/leto', ci.prenova_skupaj_m2_leto['2026_2030'], null],
    ['– od tega skupina 43 % najmanj učinkovitih', 'm²/leto', ci.wpb.m2_leto_2026_2030, null],
    ['NPS 2050: nestanovanjske stavbe za izboljšanje do 2030 (minimalni standardi, ocena)', 'število', ci.meps.n_2030, null],
    ['NPS 2050: kurilno olje v stavbah 2023 → 2030 → 2040', 'GWh/leto', `${ci.fosilna.elko.gwh_2023} → ${ci.fosilna.elko.gwh[0]} → ${ci.fosilna.elko.gwh[1]}`, null],
    ['NPS 2050: zemeljski plin v stavbah 2023 → 2030 → 2040', 'GWh/leto', `${ci.fosilna.gas.gwh_2023} → ${ci.fosilna.gas.gwh[0]} → ${ci.fosilna.gas.gwh[1]}`, null],
  ];
}
