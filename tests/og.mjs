// Slike za predogled ob deljenju povezave (Open Graph, 1200 × 630): node tests/og.mjs
// Za vsako stran iz src/content/pages/*.mdx izriše naslov v slogu naslovnice in shrani public/og/<stran>.jpg.
// Zaženi po spremembi naslovov strani. Ne potrebuje strežnika.
import { chromium } from 'playwright';
import { mkdirSync, readdirSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = process.cwd();
const out = resolve(root, 'public/og');
mkdirSync(out, { recursive: true });
// Pisave in fotografija kot data URI (stran iz setContent ne sme brati lokalnih datotek).
const data = (p, type) => `data:${type};base64,${readFileSync(resolve(root, p)).toString('base64')}`;
const font = (p) => data(`node_modules/@fontsource-variable/${p}`, 'font/woff2');
const photo = data('public/img/hero-mesto-1600.jpg', 'image/jpeg');
const esc = (s) => s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);

const pages = readdirSync(resolve(root, 'src/content/pages')).filter((f) => f.endsWith('.mdx')).map((f) => {
  const fm = readFileSync(resolve(root, 'src/content/pages', f), 'utf-8').split('---')[1];
  const get = (k) => (fm.match(new RegExp(`^${k}:\\s*'(.*)'\\s*$`, 'm')) || [])[1]?.replace(/''/g, "'");
  return { id: get('page') || fm.match(/^page:\s*(\S+)/m)[1], title: get('title') };
});

const html = (title, home) => `<!doctype html><html lang="sl"><head><meta charset="utf-8"><style>
@font-face { font-family: M; src: url(${font('manrope/files/manrope-latin-ext-wght-normal.woff2')}); font-weight: 200 800; }
@font-face { font-family: M; src: url(${font('manrope/files/manrope-latin-wght-normal.woff2')}); font-weight: 200 800; }
@font-face { font-family: S; src: url(${font('source-serif-4/files/source-serif-4-latin-ext-wght-normal.woff2')}); font-weight: 200 900; }
@font-face { font-family: S; src: url(${font('source-serif-4/files/source-serif-4-latin-wght-normal.woff2')}); font-weight: 200 900; }
* { margin: 0; box-sizing: border-box; }
body { width: 1200px; height: 630px; background: #333D22; color: #F5F2E8; font-family: M; display: grid; grid-template-rows: 1fr 190px; }
.t { padding: 56px 72px 40px; border-bottom: 2px solid #D6B25E; display: flex; flex-direction: column; }
.e { display: flex; justify-content: space-between; font-size: 20px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: #D6B25E; }
h1 { font-family: S; font-weight: 700; font-size: ${home ? 64 : 76}px; line-height: 1.06; margin-top: auto; max-width: 20ch; }
.p { background: url('${photo}') 50% 38% / cover; }
</style></head><body><div class="t"><div class="e"><span>NPS 2050 · Strokovne podlage</span><span>IJS CEU · 2026</span></div><h1>${esc(title)}</h1></div><div class="p"></div></body></html>`;

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1200, height: 630 } });
for (const p of pages) {
  await page.setContent(html(p.title, p.id === 'domov'), { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: resolve(out, `${p.id}.jpg`), type: 'jpeg', quality: 86 });
  console.log(`public/og/${p.id}.jpg`);
}
await browser.close();
