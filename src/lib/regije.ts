/** Kartice statističnih regij: podatki iz public/data/regije.json (cevovod data/npsdata/regije.py). */
import { loadData } from './data';

export interface RegObcina { sifra: number; name: string; pop: number; fe_mwh_preb: number; tgp_t_preb: number; ove_pct: number; above43_area_pct: number; semafor: string }
export interface Regija {
  id: string; name: string; n_obcin: number; buildings: number; area_k_m2: number; res_area_k_m2: number; pre1981_area_pct: number;
  vse: { pop: number; fe_gwh: Record<'res' | 'nres' | 'total', number>; tgp_kt: Record<'res' | 'nres' | 'total', number>; ove_pct: Record<'res' | 'nres' | 'total', number>;
    fe_mwh_preb: Record<'res' | 'total', number>; tgp_t_preb: Record<'res' | 'total', number> };
  fe_kwh_m2: number; carriers_pct: Record<string, number>; nps_pct: Record<string, number>; above43_area_pct: number;
  dh_pot: { fe_gwh: number; fe_pct: number; fe_ha: number };
  pot: Record<'2023' | '2030' | '2040' | '2050', { fe_gwh: number; tgp_kt: number; ove_pct: number; fossil_pct: number }>;
  cilji: { prenova_m2_leto: Record<'2026_2030' | '2031_2040', number>; wpb_m2_leto: number; meps_n_2030: number; elko_gwh: number[]; plin_gwh: number[] };
  stevilke: { hise_leto: number; stanovanja_leto: number; javne_leto: number; zasebne_leto: number; nalozba_eur_leto: number; spodbude_eur_leto: number;
    semafor: string; stopnja_dejanska_pct: number; stopnja_zahtevana_pct: number; prenov_registri: number; obcine_semafor: Record<string, number> };
  obcine: RegObcina[];
}

export const regije = () => Object.values(loadData<{ regions: Record<string, Regija> }>('regije').regions);

/** »Jugovzhodna Slovenija« → »jugovzhodna-slovenija« (pot strani kartice). */
export const regijaSlug = (name: string) =>
  name.toLowerCase().replace(/č/g, 'c').replace(/š/g, 's').replace(/ž/g, 'z').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
