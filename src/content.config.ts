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
  }),
});

export const collections = { pages };
