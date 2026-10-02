/**
 * Zemljevid strani za iskalnike: javne rubrike (brez skritih in brez iskanja) in strani 212 občin.
 * Kartice za tisk (občine, regije) se ne indeksirajo in niso vključene. Absolutni naslovi zahtevajo `site` (ASTRO_SITE v CI).
 */
import type { APIRoute } from 'astro';
import { getCollection } from 'astro:content';
import { pageUrl } from '../i18n/routes';
import { loadData, type ObcineIndex } from '../lib/data';

export const GET: APIRoute = async ({ site }) => {
  const abs = (p: string) => (site ? new URL(p, site).href : p);
  const meta = loadData<{ generated: string }>('meta');
  const pages = (await getCollection('pages')).filter((e) => !e.data.draft && e.data.page !== 'iskanje');
  const urls = [
    ...pages.map((e) => ({ loc: abs(pageUrl(e.data.page)), pr: e.data.page === 'domov' ? '1.0' : '0.8' })),
    ...loadData<ObcineIndex>('obcine_index').municipalities.map((m) => ({ loc: abs(`${pageUrl('domov')}obcina/${m.sifra}/`), pr: '0.5' })),
  ];
  const xml = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls
    .map((u) => `  <url><loc>${u.loc}</loc><lastmod>${meta.generated}</lastmod><priority>${u.pr}</priority></url>`)
    .join('\n')}\n</urlset>\n`;
  return new Response(xml, { headers: { 'Content-Type': 'application/xml; charset=utf-8' } });
};
