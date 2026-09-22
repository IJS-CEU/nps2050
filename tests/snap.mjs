// Posnetki strani za pregled (navodila projekta §8): node tests/snap.mjs [osnovni-url] [selektor ...]
// Brez selektorjev posname naslovno stran in Strokovne podlage v svetli in temni temi pri 400 in 1280 px.
// Z selektorji (npr. #graf-trajektorija) posname samo te elemente. Posnetki gredo v screenshots/ (ni v gitu).
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';

const baseUrl = (process.argv[2] || 'http://localhost:4321/').replace(/\/?$/, '/');
const selectors = process.argv.slice(3);
const pages = [['naslovna', ''], ['strokovne-podlage', 'strokovne-podlage/']];
const themes = ['light', 'dark'];
const widths = [400, 1280];

mkdirSync('screenshots', { recursive: true });
const browser = await chromium.launch();
const problems = [];

for (const theme of themes) {
  for (const width of widths) {
    const ctx = await browser.newContext({ viewport: { width, height: 900 }, colorScheme: theme, deviceScaleFactor: 1 });
    const page = await ctx.newPage();
    page.on('console', (m) => m.type() === 'error' && problems.push(`${theme} ${width}: ${m.text()}`));
    page.on('pageerror', (e) => problems.push(`${theme} ${width}: ${e.message}`));
    for (const [name, path] of selectors.length ? [['strokovne-podlage', 'strokovne-podlage/']] : pages) {
      await page.goto(baseUrl + path, { waitUntil: 'networkidle' });
      await page.waitForTimeout(600);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
      if (overflow) problems.push(`${name} ${theme} ${width}: vodoravno drsenje`);
      // Grafi ne smejo biti prazni.
      const empty = await page.$$eval('.chart-canvas', (els) => els.filter((e) => !e.querySelector('svg path')).map((e) => e.closest('figure')?.id));
      if (empty.length) problems.push(`${name} ${theme} ${width}: prazni grafi ${empty.join(', ')}`);
      if (selectors.length) {
        for (const sel of selectors) {
          const el = await page.$(sel);
          if (!el) { problems.push(`ni elementa ${sel}`); continue; }
          await el.screenshot({ path: `screenshots/${sel.replace(/\W/g, '')}-${theme}-${width}.png` });
        }
      } else {
        await page.screenshot({ path: `screenshots/${name}-${theme}-${width}.png`, fullPage: true });
      }
    }
    await ctx.close();
  }
}
await browser.close();
if (problems.length) {
  console.log('TEŽAVE:\n' + problems.map((p) => '  ' + p).join('\n'));
  process.exit(1);
}
console.log('Posnetki v screenshots/, brez težav.');
