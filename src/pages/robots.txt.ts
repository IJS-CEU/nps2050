/** robots.txt s povezavo na zemljevid strani. Na GitHub Pages v podmapi ga iskalniki ne berejo (velja le v korenu domene), zato je zemljevid prijavljen tudi v <head>. */
import type { APIRoute } from 'astro';
import { withBase } from '../i18n/routes';

export const GET: APIRoute = ({ site }) => {
  const sm = site ? new URL(withBase('sitemap.xml'), site).href : withBase('sitemap.xml');
  return new Response(`User-agent: *\nAllow: /\n\nSitemap: ${sm}\n`, { headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
};
