// @ts-check
import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';

// Stran gre najprej na GitHub Pages (podmapa), kasneje na strežnik IJS ali lastno domeno.
// Zato sta site in base nastavljiva prek okoljskih spremenljivk.
const site = process.env.ASTRO_SITE || undefined;
const base = process.env.ASTRO_BASE || '/';

export default defineConfig({
  site,
  base,
  trailingSlash: 'always',
  integrations: [mdx()],
  // ECharts (samo uporabljeni moduli) je ~190 KB gzip in se naloži le na strani s grafi.
  vite: { build: { chunkSizeWarningLimit: 600 } },
});
