/**
 * Podatki iz cevovoda (public/data/*.json) – tipi in branje ob gradnji.
 * Komponente iz njih ob gradnji izrišejo podatkovne preglednice; grafi iste datoteke naložijo v brskalniku.
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

export interface Meta { draft: string; draft_date: string; generated: string; sources: string[]; note?: string }

export interface Trajektorija {
  meta: Meta;
  kwh_m2: { unit: string; years: number[]; nps: number[]; reduction_pct: (number | null)[]; epbd_max: { year: number; max: number; min: number }[]; nps_valid_factors: number[] };
  twh: { unit: string; dec: number; years: number[]; total: number[]; total_fixed: number[]; residential: number[] };
  zgodba: {
    bands: Record<string, number>;
    wpb: { area_mio_m2: number; avg_pe_2020: number; target_bc: number; years: number[]; renovated_pct: number[] };
    scenarios: { years: number[]; S0: number[]; S1: number[]; S2: number[]; names: Record<string, string> };
    cilji: { id: string; label: string; unit: string; dec: number; base2020: number | null; base2023: number; years: Record<string, { value: number; vs2023: number; vs2020: number | null }> }[];
  };
}

export interface Category {
  id: string; name: string; segment: 'stanovanjske' | 'nestanovanjske';
  buildings: number; area_mio_m2: number; public_buildings: number | null; public_area_mio_m2: number | null;
  heated_area_2020_mio_m2: number | null;
  by_period: { buildings: (number | null)[]; area_mio_m2: number[] };
  class_bounds: Record<string, number>;
  worst_43?: { threshold: number; area_share_pct: number; avg_pe_above: number };
  meps?: {
    threshold_2030: number; threshold_2033: number; indicative: boolean;
    covered_2030: { buildings: number; area_mio_m2: number }; covered_2033: { buildings: number; area_mio_m2: number };
    stock_to_2020: { buildings: number; area_mio_m2: number };
  };
}
export interface StavbniFond {
  meta: Meta; periods: string[];
  segments: Record<string, { buildings: number; area_mio_m2: number; heated_area_2020_mio_m2: number | null }>;
  categories: Category[];
}

export type Scen = 'S0' | 'S1' | 'S2';
export interface Series { years: number[]; S0: number[]; S1: number[]; S2: number[] }
export interface Scenariji {
  meta: Meta;
  nps: {
    years: number[];
    sectors: { id: string; name: string }[];
    indicators: Record<string, { unit: string; dec: number; sectors: string[]; values: Record<string, number[]> }>;
  };
  primerjava: {
    scenarios: { id: Scen; name: string }[];
    fe_index: Series; pe_index_2050: Record<Scen, number>; pe_res_fixed_index: Series; worst_fg_share_pct: Series;
    table: { label: string; unit: string; values: Record<Scen, string> }[];
  };
}

export interface KazalnikValue { year: number; text: string; value: number | null; range?: [number, number] }
export interface Kazalnik {
  id: string; label: string; unit: string; dec?: number; chart: boolean;
  baseline: { text: string; value: number | null; year: number | null };
  values: KazalnikValue[];
}
export interface Kazalniki { meta: Meta; years: number[]; items: Kazalnik[] }

export function loadData<T>(name: string): T {
  return JSON.parse(readFileSync(resolve(process.cwd(), 'public', 'data', `${name}.json`), 'utf-8')) as T;
}

export interface SankeyType {
  name: string; years: number[];
  nodes: { name: string; class: string; year: number; value: number }[];
  links: { source: string; target: string; value: number }[];
  totals: Record<string, number>;
}
export interface Sankey { meta: Meta; classes: string[]; types: Record<string, SankeyType> }

export interface Area {
  name: string; region?: string; buildings: number; area_k_m2: number; res_area_k_m2: number; nonres_area_k_m2: number;
  pre1981_area_pct: number | null; cats: Record<string, { b: number; a: number } | null>;
  w_res_model_pct?: number | null; w_res_reg_pct?: number | null; w_res_reg_n?: number; w_nres_reg_pct?: number | null; w_nres_reg_n?: number;
}
export interface Zemljevid {
  meta: Meta; categories: { id: string; name: string; segment: string }[];
  regions: Record<string, Area>; municipalities: Record<string, Area>;
}

export interface Activity { kind: string; resp: string; text: string; deadline: string; kpi: string; target: string }
export interface Measure {
  id: string; group: 'nepn' | 'nepn_novi' | 'nps'; group_label: string; name: string; areas: string[];
  activities: Activity[]; kinds: string[]; responsible: string[]; first_deadline: number | null; recurring: boolean;
}
export interface Ukrepi {
  meta: Meta; areas: Record<string, { name: string; content: string }>; kinds: { id: string; name: string }[];
  measures: Measure[];
  boilers: { when: string; milestone: string; basis: string; effect: string }[];
  investments: { periods: string[]; segments: Record<string, Record<string, (number | null)[]>>; total_2026_2030: number; total_2026_2050: number; gap_2026_2030: number };
  sources: { source: string; period: string; amount: string; purpose: string }[];
}

export interface PrihranekRow { class: string; area_mio_m2: number; sfh_use: number; sfh_saving: number; mfh_use: number; mfh_saving: number; per_euro_vs_c: string }
export interface Prihranek { meta: Meta; after: { sfh: number; mfh: number }; rows: PrihranekRow[] }

export interface Revscina {
  meta: Meta;
  by_type_avg: number;
  share: { years: number[]; base: number; base_year: number; target_2030: [number, number]; target_2040: number; target_2050: number };
  counts_2024: { households: number; persons: number; cannot_heat: number; arrears: number; leaks_damp: number };
  by_type_2024: { name: string; pct: number }[];
  investments_2030: { households: number; cumulative_gwh: number };
}

export interface ObSegment { buildings: number | null; area_k_m2: number | null; ei_buildings_pct: number | null; ei_area_pct: number | null; ei_calc: number | null; classes_pct: Record<string, number> | null; class_groups_pct: Record<string, number> | null }
export interface ObArea {
  buildings: number; area_k_m2: number;
  segments: Record<string, ObSegment>;
  res_period_area_pct: Record<string, number | null>;
  res_above43_pct: number | null; nres_above_meps30_pct: number | null; nres_above_meps33_pct: number | null; nres_ei_calc: number | null;
  es_res: Record<string, { b: number | null; pct: number | null }>; es_res_any_pct: number | null;
  obnova_res_pct: number | null; obnova_res_since2010_pct: number | null; res_ei_calc: number;
  public_by_cat: Record<string, { b: number | null; a: number | null }>;
}
export interface ObIndexRow {
  sifra: number; eid: string; name: string; region: string; buildings: number; area_k_m2: number;
  ei_area_res_pct: number | null; hise_ei_pct: number | null; res_above43_pct: number | null; es_res_any_pct: number | null;
  obnova_res_pct: number | null; pre1981_res_area_pct: number | null;
  model_fe_kwh_m2: number; model_above43_pct: number;
  k_fe_mwh_preb: number; k_res_fe_mwh_preb: number; k_tgp_t_preb: number; k_ove_pct: number; k_nres_kwh_m2: number | null; k_dh_pot_pct: number; k_dh_fe_pct: number; pop: number;
  w_res_model_pct: number | null; w_res_reg_pct: number | null; w_res_reg_n: number; w_nres_reg_pct: number | null; w_nres_reg_n: number;
}
export interface ObcineIndex {
  meta: Meta; min_cell: number; min_ei: number; classes: string[]; class_groups: string[]; periods: string[];
  segments: { id: string; name: string }[]; es_groups: { id: string; name: string }[]; categories: { id: string; name: string }[];
  si: ObArea & { ei_area_res_pct: number; pre1981_res_area_pct: number; model_fe_kwh_m2: number; model_above43_pct: number; k_fe_mwh_preb: number; k_res_fe_mwh_preb: number; k_tgp_t_preb: number; k_ove_pct: number; k_nres_kwh_m2: number | null; k_dh_pot_pct: number; k_dh_fe_pct: number; pop: number; w_res_model_pct: number | null; w_res_reg_pct: number | null; w_res_reg_n: number; w_nres_reg_pct: number | null; w_nres_reg_n: number };
  municipalities: ObIndexRow[];
}
export interface Obcina extends ObArea { meta: Meta; sifra: number; eid: string; name: string; region: string; region_name: string }

export interface ObModelArea {
  fe_gwh: number; fe_gwh_lo: number; fe_gwh_hi: number; fe_kwh_m2: number; pe_gwh: number; pe_kwh_m2: number;
  carriers_pct: Record<string, number>; nps_pct: Record<string, number>; above43_area_pct: number; known_pct: number; tk_factor?: number; name?: string;
  vse: ObVse;
  cilji?: ObCilji;
  dh_pot?: { q_gwh: number; dense_gwh: number; pct: number; ha: number; fe_gwh: number; fe_dense_gwh: number; fe_pct: number; fe_ha: number };
  javne_cat?: Record<string, { b: number; kwh_m2: number | null; meas_pct: number | null }>;
  pot?: Record<string, { fe_gwh: number; fe_res_gwh: number; tgp_kt: number; ove_pct: number | null; fossil_pct: number | null }>;
}
export interface ObSkupine { groups: { id: string; name: string; n: number }[]; municipalities: Record<string, { group: string; neighbours: number[]; density: number; hotel_m2_preb: number }> }
export interface ObCilji {
  prenova_m2_leto: Record<string, { '2026_2030': number; '2031_2040': number }>;
  prenova_skupaj_m2_leto: { '2026_2030': number; '2031_2040': number };
  wpb: { area_m2: number; m2_leto_2026_2030: number; cum_pct: Record<string, number> };
  fosilna: Record<string, { gwh_2023: number; gwh: number[] }>;
  meps: { nres_buildings: number; n_2030: number; n_2033: number; local_ei: boolean };
}
export interface ObVse {
  pop: number; fe_gwh: { res: number; nres: number; total: number }; tgp_kt: { res: number; nres: number; total: number };
  ove_pct: { res: number | null; nres: number | null; total: number | null }; fe_mwh_preb: { res: number; total: number }; tgp_t_preb: { res: number; total: number };
  nres_kwh_m2: number | null; nres_measured_area_pct: number | null; dh_ove_pct: number | null;
}
export interface ObcineModel { meta: Meta; carriers: { id: string; name: string }[]; classes: string[]; si: ObModelArea & { pot: Record<string, { fe_gwh: number; tgp_kt: number }> }; municipalities: Record<string, ObModelArea> }
