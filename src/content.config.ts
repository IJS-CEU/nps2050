import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';
import { pageIds } from './i18n/routes';

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

export const collections = { pages, dnevnik };
