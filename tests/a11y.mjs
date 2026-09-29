// Preverjanje dostopnosti (WCAG 2.1 AA) z axe: node tests/a11y.mjs [osnovni-url]
// Vseh 7 strani, svetla in temna tema, 400 in 1280 px; preglednice pod grafi so odprte, da se preverijo tudi one.
// Izhod 1, če je kakšna kršitev stopnje »critical« ali »serious«.
import { chromium } from 'playwright';
import { AxeBuilder } from '@axe-core/playwright';

const baseUrl = (process.argv[2] || 'http://localhost:4321/').replace(/\/?$/, '/');
const paths = ['', 'kaj-je-nps-2050/', 'za-lastnike/', 'strokovne-podlage/', 'javna-obravnava/', 'dokumenti/', 'preveri-stavbo/', 'za-medije/', 'ukrepi-in-financiranje/', 'ne-obstaja/'];
const browser = await chromium.launch();
const found = new Map();

for (const colorScheme of ['light', 'dark']) {
  for (const width of [400, 1280]) {
    const ctx = await browser.newContext({ viewport: { width, height: 900 }, colorScheme });
    const page = await ctx.newPage();
    for (const p of paths) {
      await page.goto(baseUrl + p, { waitUntil: 'networkidle' });
      await page.evaluate(() => document.querySelectorAll('details').forEach((d) => (d.open = true)));
      await page.waitForTimeout(300);
      const res = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
      for (const v of res.violations) {
        const key = `${v.impact} · ${v.id} · /${p}`;
        const prev = found.get(key) ?? { v, where: new Set() };
        prev.where.add(`${colorScheme} ${width}`);
        found.set(key, prev);
      }
    }
    await ctx.close();
  }
}
await browser.close();

let bad = 0;
for (const [key, { v, where }] of [...found].sort()) {
  if (v.impact === 'critical' || v.impact === 'serious') bad++;
  console.log(`${key}  [${[...where].join(', ')}]\n   ${v.help}\n   ${v.nodes.slice(0, 3).map((n) => n.target.join(' ') + ' – ' + (n.failureSummary || '').split('\n').slice(1, 2).join('')).join('\n   ')}`);
}
console.log(found.size ? `\n${found.size} vrst kršitev, od tega ${bad} kritičnih ali resnih.` : 'Brez kršitev.');
process.exit(bad ? 1 : 0);
