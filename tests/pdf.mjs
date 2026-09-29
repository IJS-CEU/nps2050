// Povzetek NPS 2050 v PDF (5 strani A4): node tests/pdf.mjs [osnovni-url]
// Natisne /povzetek-tisk/ z zagnanega strežnika (npm run build && npm run preview) v public/nps2050-povzetek.pdf.
// Zaženi po vsaki osvežitvi podatkov in nato še enkrat zgradi stran.
import { chromium } from 'playwright';

const baseUrl = (process.argv[2] || 'http://localhost:4321/').replace(/\/?$/, '/');
const out = 'public/nps2050-povzetek.pdf';
const browser = await chromium.launch();
const page = await browser.newPage();
await page.goto(baseUrl + 'povzetek-tisk/', { waitUntil: 'networkidle' });
await page.evaluate(() => document.fonts.ready);
const n = await page.locator('section.pg').count();
// Vsebina ne sme segati v nogo strani (zadnji element nad črto noge).
const overflow = await page.$$eval('section.pg', (pgs) => pgs.map((pg, i) => {
  const foot = pg.querySelector('.pf').getBoundingClientRect().top;
  const last = [...pg.querySelectorAll('.in > *')].reduce((m, e) => Math.max(m, e.getBoundingClientRect().bottom), 0);
  return last > foot - 4 ? i + 1 : 0;
}).filter(Boolean));
if (n !== 5) throw new Error(`pričakovanih 5 strani, najdenih ${n}`);
if (overflow.length) throw new Error(`vsebina presega stran: ${overflow.join(', ')}`);
await page.pdf({ path: out, format: 'A4', printBackground: true, preferCSSPageSize: true,
  tagged: true, outline: false });
await browser.close();
console.log(out);
