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
  streha: [[22, 28], [15, 20], [11, 15]],   // NPS: referenca 11 je brez zgornje meje na m², kalkulator mejo poveča sorazmerno (52,5 €/m²)
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

test('vsota prihrankov ukrepov na ovoju je enaka prihranku paketa (hiša 1981–2002, delno izolirana)', () => {
  const r = izracun(D, { povrsina: 110, obdobje: '1981_2002', stanje: 'delno', energent: 'kurilno_olje', ukrepi: ['fasada', 'plosca_podstrehe', 'okna'] });
  const vsota = r.rezultati.reduce((s, x) => s + x.prihranek_eur, 0);
  assert.ok(Math.abs(vsota - r.paket.prihranek_eur) < 1, `${vsota.toFixed(0)} = ${r.paket.prihranek_eur.toFixed(0)}`);
  assert.ok(r.paket.brez && r.paket.brez.ukrepi.includes('okna'), 'paket brez oken');
  assert.ok(r.paket.brez.doba[1] < r.paket.doba[1]);
});
test('stanovanje v bloku do 1980, daljinsko: fasada in okna okoli 27 let brez spodbude (Qh,nd iz izkaznic)', () => {
  const r = izracun(D, { tip: 'blok', povrsina: 59, obdobje: 'pred_1980', stanje: 'neizoliran', energent: 'daljinska_toplota', ukrepi: ['fasada', 'okna', 'tc', 'plosca_podstrehe'] });
  assert.deepEqual(r.rezultati.map((x) => x.ukrep), ['fasada', 'okna'], 'v bloku ni črpalke in plošče');
  v(r.paket.doba[0], [24, 30], 'blok fasada + okna');
  assert.ok(r.paket.doba[2] < r.paket.doba[1]);
});

test('sončna elektrarna: letni net metering ≥ mesečni > nova shema (odkup 0); pozimi pokrije manj kot tretjino elektrike s črpalko', async () => {
  const r = izracun(D, { ...base, ukrepi: ['tc', 'pv'] });
  const z = r.pv.rezimi;
  assert.ok(z.letni.prihranek_eur >= z.mesecni.prihranek_eur && z.mesecni.prihranek_eur > z.nova.prihranek_eur, `${z.letni.prihranek_eur} ≥ ${z.mesecni.prihranek_eur} > ${z.nova.prihranek_eur}`);
  assert.equal(z.letni.prodano_kwh, 0, 'letni presežek ni plačan');
  assert.ok(Math.abs(r.pv.proizvodnja_kwh / r.pv.kw - 1167) < 2, 'PVGIS 1.167 kWh/kW');
  assert.ok(r.pv.pokritost_zima < 0.35, `zima ${r.pv.pokritost_zima}`);
});
test('opozorilo URE: črpalka ali elektrarna na neizolirani hiši brez ovoja, ne pa z ovojem', async () => {
  const { opozorila, PRIVZETO } = await import('../src/scripts/povracilo.ts');
  const o = (uk) => opozorila(D, { ...base, ukrepi: uk }, PRIVZETO, izracun(D, { ...base, ukrepi: uk })).map((x) => x.tip);
  assert.deepEqual(o(['tc']), ['tc', 'najslabse']);
  assert.ok(o(['pv']).includes('pv'));
  assert.deepEqual(o(['fasada', 'tc', 'pv']), []);
});
test('prenova po korakih: celovita prenova z elektrarno doseže ZEB, brez elektrarne ne; črpalka pred ovojem je prevelika', async () => {
  const { nacrt, PRIPOROCEN, PRIVZETO } = await import('../src/scripts/povracilo.ts');
  const uk = ['fasada', 'plosca_podstrehe', 'okna', 'tc'];
  const k = (u) => u.map((x) => ({ ukrep: x, leto: PRIPOROCEN[x] }));
  const a = nacrt(D, { ...base, ukrepi: [] }, PRIVZETO, k(uk));
  const b = nacrt(D, { ...base, ukrepi: [] }, PRIVZETO, k([...uk, 'pv']));
  assert.ok(!a.konec.zeb && b.konec.zeb, `${a.konec.pe_m2} / ${b.konec.pe_m2}`);
  assert.equal(a.bonus_korak, D.spodbude.predlog_NPS_N1.bonus_celovita);
  assert.ok(a.skupaj.poziv < a.skupaj.brez, 'prenova je v 20 letih cenejša od hiše brez prenove');
  const c = nacrt(D, { ...base, ukrepi: [] }, PRIVZETO, [{ ukrep: 'tc', leto: 0 }, { ukrep: 'fasada', leto: 5 }]);
  assert.ok(c.prevelika && c.prevelika.moc > c.prevelika.moc_konec);
  assert.equal(c.bonus_korak, D.spodbude.predlog_NPS_N1.bonus_korak_izkaz);
});

test('izpis prenove: delne prenove, naenkrat, najprej URE in najprej OVE; najprej OVE je dražje', async () => {
  const { variante, razred, PRIVZETO } = await import('../src/scripts/povracilo.ts');
  const V = variante(D, { ...base, ukrepi: ['fasada', 'tc', 'pv'] }, PRIVZETO);
  assert.deepEqual(V.map((x) => x.skupina), ['delna', 'delna', 'delna', 'delna', 'naenkrat', 'ure', 'ove']);
  assert.deepEqual(V.filter((x) => x.skupina === 'delna').map((x) => x.ukrepi.join('+')), ['fasada', 'tc', 'pv', 'tc+pv']);
  const ure = V.find((x) => x.skupina === 'ure').N, ove = V.find((x) => x.skupina === 'ove').N;
  assert.ok(ove.skupaj.poziv > ure.skupaj.poziv && ove.prevelika, `${ove.skupaj.poziv} > ${ure.skupaj.poziv}`);
  const M = [75, 166, 257, 347, 438, 529];
  assert.equal(razred(60, M), 'A'); assert.equal(razred(300, M), 'D'); assert.equal(razred(600, M), 'G');
  assert.equal(variante(D, { ...base, ukrepi: ['fasada', 'plosca_podstrehe', 'okna', 'prezracevanje', 'tc', 'pv'] }, PRIVZETO).filter((x) => x.skupina === 'delna').length, 6, 'ovoj kot ena enota, vsi URE in vsi OVE');
});

test('razred: kalkulator je umerjen na izkaznice kot paketi prenove (olje do 1980: D, po fasadi in oknih C; celovita s prezračevanjem in črpalko A)', async () => {
  const { nacrt, razred, PRIVZETO } = await import('../src/scripts/povracilo.ts');
  const P = JSON.parse(readFileSync(new URL('../public/data/paketi_prenove.json', import.meta.url), 'utf-8'));
  const h = P.tipi.find((t) => t.id === 'hisa_do1980').variante.find((x) => x.id === 'olje');
  assert.equal(D.model.pe_izkaznice_neprenovljene.pred_1980.olje, h.pe_pred, 'kopija iz paketov prenove je aktualna');
  const M = [75, 166, 257, 347, 438, 529];
  const k = (uk, extra = {}) => nacrt(D, { ...base, ...extra, ukrepi: [] }, PRIVZETO, uk.map((u) => ({ ukrep: u, leto: 0 })));
  const a = k(['fasada', 'okna']);
  assert.equal(razred(a.zacetek.pe_m2, M), h.razred_pred);
  assert.equal(razred(a.konec.pe_m2, M), h.paketi.find((x) => x.id === 'delna').razred_po);
  assert.equal(razred(k(['fasada', 'streha', 'okna', 'prezracevanje', 'tc'], { prezracevanje: 'centralno' }).konec.pe_m2, M), 'A');
});
test('stroški v 20 letih: zamenjava črpalke po 18 letih in preostala vrednost ovoja', async () => {
  const { nacrt, PRIVZETO } = await import('../src/scripts/povracilo.ts');
  const n = nacrt(D, { ...base, ukrepi: [] }, PRIVZETO, [{ ukrep: 'fasada', leto: 0 }, { ukrep: 'tc', leto: 0 }]);
  assert.equal(n.zamenjave.length, 1); assert.equal(n.zamenjave[0].leto, 18);
  assert.ok(n.ostanek.poziv > 0);
});

test('stanovanje v bloku: razred umerjen na izkaznice kot paketi prenove (do 1980: E, po fasadi in oknih C)', async () => {
  const { nacrt, razred, PRIVZETO } = await import('../src/scripts/povracilo.ts');
  const P = JSON.parse(readFileSync(new URL('../public/data/paketi_prenove.json', import.meta.url), 'utf-8'));
  const h = P.tipi.find((t) => t.id === 'blok_do1980').variante[0];
  const M = [75, 124, 173, 223, 272, 321];
  const vb = { tip: 'blok', povrsina: 59, obdobje: 'pred_1980', stanje: 'neizoliran', energent: 'daljinska_toplota', ukrepi: [] };
  const a = nacrt(D, vb, PRIVZETO, [{ ukrep: 'fasada', leto: 0 }, { ukrep: 'okna', leto: 0 }]);
  assert.equal(razred(a.zacetek.pe_m2, M), h.razred_pred);
  assert.equal(razred(a.konec.pe_m2, M), h.paketi.find((x) => x.id === 'delna').razred_po);
  const c = nacrt(D, vb, PRIVZETO, ['fasada', 'streha', 'okna', 'prezracevanje'].map((u) => ({ ukrep: u, leto: 0 })));
  assert.equal(razred(c.konec.pe_m2, M), 'A');
  assert.ok(c.konec.zeb);
});

test('fasada, streha, črpalka in elektrarna: razred A in ZEB; brez elektrarne ne', async () => {
  const { nacrt, razred, PRIVZETO } = await import('../src/scripts/povracilo.ts');
  const M = [75, 166, 257, 347, 438, 529];
  const k = (uk) => nacrt(D, { ...base, ukrepi: [] }, PRIVZETO, uk.map((u) => ({ ukrep: u, leto: 0 })));
  const a = k(['fasada', 'streha', 'tc', 'pv']), b = k(['fasada', 'streha', 'tc']);
  assert.equal(razred(a.konec.pe_m2, M), 'A'); assert.ok(a.konec.zeb);
  assert.ok(!b.konec.zeb, `brez elektrarne ${b.konec.pe_m2}`);
});
test('rast cen in ETS2 podražita hišo brez prenove na kurilno olje', async () => {
  const { nacrt, PRIVZETO } = await import('../src/scripts/povracilo.ts');
  const kor = [{ ukrep: 'fasada', leto: 0 }];
  const s = (n) => nacrt(D, { ...base, ukrepi: [] }, { ...PRIVZETO, ...n }, kor).brez.at(-1);
  const stalne = s({ rast: 0, ets2: 0 }), ets = s({ rast: 0 }), oboje = s({});
  assert.ok(stalne < ets && ets < oboje, `${stalne} < ${ets} < ${oboje}`);
  assert.ok(Math.abs(stalne - 20 * nacrt(D, { ...base, ukrepi: [] }, { ...PRIVZETO, rast: 0, ets2: 0 }, kor).energija_zacetek) < 20, 'brez rasti in ETS2 = 20 × današnji stroški');
});
