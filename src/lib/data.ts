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
  ktoe: { unit: string; years: number[]; total: number[]; total_fixed: number[]; residential: number[] };
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
    indicators: Record<string, { unit: string; sectors: string[]; values: Record<string, number[]> }>;
  };
  primerjava: {
    scenarios: { id: Scen; name: string }[];
    fe_index: Series; pe_index_2050: Record<Scen, number>; pe_res_fixed_index: Series; worst_fg_share_pct: Series;
    table: { label: string; unit: string; values: Record<Scen, string> }[];
  };
}

export interface KazalnikValue { year: number; text: string; value: number | null; range?: [number, number] }
export interface Kazalnik {
  id: string; label: string; unit: string; chart: boolean;
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
