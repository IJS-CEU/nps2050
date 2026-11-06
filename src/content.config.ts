import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';
import { pageIds } from './i18n/routes';
import { SKUPINE, TEME } from './lib/vprasanja';

// Ena datoteka MDX na rubriko: src/content/pages/<id>.mdx
const pages = defineCollection({
  loader: glob({ pattern: '**/*.mdx', base: './src/content/pages' }),
  schema: z.object({
    page: z.enum(pageIds),
    title: z.string(),
    description: z.string(),
    lead: z.string().optional(),
    /** Nova rubrika do potrditve (CLAUDE.md §11): zgradi se, a ima noindex in ni v navigaciji. */
    draft: z.boolean().optional(),
  }),
});

// 11.9 Dnevnik sprememb: en vnos na datoteko src/content/dnevnik/<datum>-<ime>.md
const dnevnik = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/dnevnik' }),
  schema: z.object({
    datum: z.string(),
    naslov: z.string(),
    vrsta: z.enum(['rocni', 'samodejni']),
    osnutek: z.string().optional(),
    osnutek_datum: z.string().optional(),
  }),
});

// 11.5 Napačna razumevanja: en vnos na datoteko src/content/napacna-razumevanja/<nn>-<ime>.md
const napacna = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/napacna-razumevanja' }),
  schema: z.object({
    trditev: z.string(),
    drzi: z.enum(['ne', 'delno']),
    vir: z.string(),
    povezava: z.enum(pageIds),
    /** prikaži tudi na strani Za lastnike */
    lastniki: z.boolean().default(false),
  }),
});

// Vprašanja deležnikov: en vnos na datoteko src/content/vprasanja/<nn>-<ime>.md, besedilo = odgovor
const vprasanja = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/vprasanja' }),
  schema: z.object({
    vprasanje: z.string(),
    skupine: z.array(z.enum(Object.keys(SKUPINE) as [keyof typeof SKUPINE, ...(keyof typeof SKUPINE)[]])).min(1),
    tema: z.enum(Object.keys(TEME) as [keyof typeof TEME, ...(keyof typeof TEME)[]]),
    /** datum objave odgovora */
    datum: z.string(),
    /** število vprašanj iz obrazca, ki jih odgovor združuje (0 = začetno vprašanje uredništva) */
    zdruzeno: z.number().int().default(0),
    povezava: z.enum(pageIds).optional(),
  }),
});

export const collections = { pages, dnevnik, napacna, vprasanja };
