// Enotski testi kalkulatorja »Se mi splača?«: node --test tests/povracilo.test.mjs
// Referenčni rezultati (Navodila_za-lastnike_povracilne-dobe.md, razdelek 5): hiša 110 m², pred letom 1980, neizoliran ovoj,
// povračilna doba brez spodbude / poziv 2026 / predlog NPS (F in G); ujemanje znotraj ±20 % od razpona.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { izracun, mocTC, stanjePo } from '../src/scripts/povracilo.ts';

const D = JSON.parse(readFileSync(new URL('../src/data/povracilne_dobe.json', import.meta.url), 'utf-8'));
const base = { povrsina: 110, obdobje: 'pred_1980', stanje: 'neizoliran', energent: 'kurilno_olje' };
const doba = (ukrep, energent = 'kurilno_olje') => izracun(D, { ...base, energent, ukrepi: [ukrep] }).rezultati[0].doba;
const v = (x, [lo, hi], what) => {
  assert.ok(x != null, `${what}: se ne povrne`);
  assert.ok(x >= lo * 0.8 && x <= hi * 1.2, `${what}: ${x.toFixed(1)} let, pričakovano ${lo}–${hi} (±20 %)`);
};

const REF = {
  fasada: [[16, 19], [9, 11], [6, 8]],
  plosca_podstrehe: [[16, 20], [9, 12], [6, 8]],
  streha: [[22, 28], [15, 20], [11, 11]],
};
for (const [u, r] of Object.entries(REF)) {
  test(`ovoj: ${u}`, () => { const d = doba(u); r.forEach((rr, i) => v(d[i], rr, `${u} [${i}]`)); });
}
test('okna: več kot 50 let brez spodbude, s pozivom več kot 40', () => { const d = doba('okna'); assert.ok(d[0] > 50 && d[1] > 40, d.join(' / ')); });

const TC = { kurilno_olje: [[9, 10], [5, 5.5], [3.5, 3.5]], zemeljski_plin: [[20, 23], [11, 12.5], [7, 7]], peleti: [[44, 50], [24, 28], [16, 16]] };
for (const [e, r] of Object.entries(TC)) {
  test(`toplotna črpalka namesto: ${e}`, () => { const d = doba('tc', e); r.forEach((rr, i) => v(d[i], rr, `TČ ${e} [${i}]`)); });
}
test('toplotna črpalka namesto polen: brez povračila', () => { assert.deepEqual(doba('tc', 'polena'), [null, null, null]); });

test('ovoj z črpalko zmanjša moč in ceno črpalke', () => {
  const r = izracun(D, { ...base, ukrepi: ['fasada', 'plosca_podstrehe', 'tc'] });
  const tc = r.rezultati.find((x) => x.ukrep === 'tc');
  assert.ok(tc.moc_kw < tc.moc_brez_ovoja_kw, `${tc.moc_kw} < ${tc.moc_brez_ovoja_kw} kW`);
  assert.ok(tc.strosek < tc.strosek_brez_ovoja);
  assert.equal(r.rezultati.at(-1).ukrep, 'tc', 'ovoj pred črpalko');
  assert.ok(r.paket.prihranek_eur > 0 && r.paket.doba[1] < r.paket.doba[0]);
});
test('stanje po ukrepih in moč', () => {
  assert.equal(stanjePo('neizoliran', ['fasada', 'streha']), 'izoliran');
  assert.equal(stanjePo('neizoliran', ['fasada']), 'delno');
  assert.equal(mocTC(D, 16500), 10);
});
test('predlog NPS ne preseže 70 %', () => {
  const r = izracun(D, { ...base, ukrepi: ['fasada', 'streha', 'tc'] });
  for (const x of r.rezultati) assert.ok(x.spodbuda_nps <= x.strosek * 0.7 + 1e-6);
});

test('dve hiši: najprej fasada je ceneje in z manjšo črpalko', async () => {
  const { dveHisi } = await import('../src/scripts/povracilo.ts');
  const S = JSON.parse(readFileSync(new URL('../src/data/dve_hisi.json', import.meta.url), 'utf-8'));
  const r = dveHisi(D, S);
  const [a, b] = r.scenariji;
  assert.ok(b.skupaj < a.skupaj, `${b.skupaj} < ${a.skupaj}`);
  assert.ok(b.moc < a.moc && b.elektrika_kwh < a.elektrika_kwh);
  assert.ok(b.skupaj < r.brez.at(-1), 'prenova je cenejša od neprenovljene hiše v 20 letih');
});
