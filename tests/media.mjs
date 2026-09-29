// Grafi za medije (PNG z naslovom in virom, svetla tema): node tests/media.mjs [osnovni-url]
// Uporabi isti izvoz kot gumb »PNG« pod grafom in shrani v public/mediji/. Zaženi po vsaki osvežitvi podatkov.
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';

const baseUrl = (process.argv[2] || 'http://localhost:4321/').replace(/\/?$/, '/');
const out = 'public/mediji';
// [datoteka, id grafa, izbire (id radijskih gumbov) pred izvozom]
const charts = [
  ['nps2050-trajektorija', 'graf-trajektorija', ['traj-mode-kwh']],
  ['nps2050-stavbni-fond', 'graf-fond', ['fond-mera-area']],
  ['nps2050-koncna-energija', 'graf-scenariji', ['sc-tab-nps', 'sc-ind-koncna_energija']],
  ['nps2050-primerjava-strategij', 'graf-scenariji', ['sc-tab-cmp', 'sc-ser-fe_index']],
];

mkdirSync(out, { recursive: true });
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1100, height: 900 }, colorScheme: 'light', reducedMotion: 'reduce', acceptDownloads: true });
const page = await ctx.newPage();
await page.goto(baseUrl + 'strokovne-podlage/', { waitUntil: 'networkidle' });
for (const [file, id, picks] of charts) {
  for (const p of picks) await page.click(`label[for="${p}"]`);
  await page.waitForTimeout(300);
  const [dl] = await Promise.all([page.waitForEvent('download'), page.click(`#${id} [data-dl="png"]`)]);
  await dl.saveAs(`${out}/${file}.png`);
  console.log(`${out}/${file}.png`);
}
await browser.close();
