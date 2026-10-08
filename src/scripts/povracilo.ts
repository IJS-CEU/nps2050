// Kalkulator »Se mi splača?« – čiste funkcije (brez DOM), enostavne nediskontirane povračilne dobe.
// Podatki: src/data/povracilne_dobe.json (Eko sklad 2023–2025, poziva 126SUB-OB26 in 124SUB-OBPO25, SURS, Agencija za energijo,
// analiza vgradenj TČ, osnutek NPS 2050). Testi: tests/povracilo.test.mjs.
//
// Hiša ali stanovanje v bloku. Prihranek ukrepa na ovoju: površina × (U_pred − U_po) × 45 kKh × faktor po stanju ovoja,
// sorazmerno zmanjšan tako, da vsi ukrepi na ovoju skupaj ne prihranijo več od razlike do stanja po celoviti prenovi (tabela Qh,nd).
// Tako se vsota prihrankov posameznih ukrepov ujema s prihrankom paketa, pri novejših in že delno izoliranih stavbah pa
// prihranek ni precenjen (dejanska raba je nižja od računske).
//
// Sončna elektrarna (samo hiše): mesečna bilanca proizvodnje (PVGIS) in rabe elektrike (gospodinjstvo + ogrevanje po stopinjskih
// dnevih) za tri načine obračuna – letni net metering (stara shema), nova shema samooskrbe od leta 2024 (mesečni obračun v evrih:
// sproti porabljena elektrika zmanjša nakup, oddana se proda po odkupni ceni) in hipotetični mesečni net metering. Prenova po korakih (nacrt):
// kumulativni stroški, ko se ukrepi izvedejo v različnih letih, ocena primarne energije in pogojev za brezemisijsko stavbo (ZEB).

export type Tip = 'hisa' | 'blok';
export type Obdobje = 'pred_1980' | '1981_2002' | 'po_2002';
export type Stanje = 'neizoliran' | 'delno' | 'izoliran' | 'celovita';
export type Energent = 'kurilno_olje' | 'zemeljski_plin' | 'peleti' | 'polena' | 'elektrika' | 'daljinska_toplota';
export type Ukrep = 'fasada' | 'streha' | 'plosca_podstrehe' | 'okna' | 'prezracevanje' | 'tc' | 'pv';
export type Obracun = 'letni' | 'nova' | 'mesecni';
export const OBRACUNI: Obracun[] = ['letni', 'nova', 'mesecni'];
export const OVOJ: Ukrep[] = ['fasada', 'streha', 'plosca_podstrehe', 'okna'];
export const UKREPI_BLOK: Ukrep[] = ['fasada', 'streha', 'okna', 'prezracevanje'];

export interface Vhod {
  tip?: Tip;                      // privzeto hiša
  povrsina: number;               // ogrevana površina hiše ali stanovanja, m²
  obdobje: Obdobje;
  stanje: Exclude<Stanje, 'celovita'>;
  energent: Energent;
  raba_kwh?: number | null;       // letna raba energenta za ogrevanje (neobvezno)
  ukrepi: Ukrep[];
  tc_vrsta?: 'zrak_voda' | 'zemlja_voda';
  prezracevanje?: 'lokalno' | 'centralno';
  stroski?: Partial<Record<Ukrep, number>>;   // uporabnikova ponudba v €
  razred?: string | null;         // iz orodja Preveri stavbo (A–G)
  nad43?: boolean | null;         // stavba med 43 % najmanj učinkovitimi
  pv_kw?: number | null;          // moč sončne elektrarne (privzeto po rabi elektrike)
  raba_gosp_kwh?: number | null;  // raba elektrike v gospodinjstvu brez ogrevanja
}

export interface Nastavitve {
  cena_el: number;                // faktor cene elektrike (1 = privzeta)
  cena_en: number;                // faktor cene sedanjega energenta
  strosek: number;                // faktor stroška naložbe
  spodbuda: number | null;        // enoten delež spodbude (0–0,7) namesto pravil poziva; null = pravila pozivov
  odkup?: number | null;          // odkupna cena presežkov elektrike [€/kWh]; null = privzeta
  rast?: number | null;           // rast cen energije na leto (0,02 = 2 %) za stroške v več letih; null = privzeta
  ets2?: number | null;           // cena CO₂ v ETS2 [€/t] od leta uvedbe za kurilno olje in plin; null = privzeta, 0 = brez
}
export const PRIVZETO: Nastavitve = { cena_el: 1, cena_en: 1, strosek: 1, spodbuda: null };

export interface Rezultat {
  ukrep: Ukrep; ime: string; strosek: number; zivljenjska_doba: number;
  prihranek_kwh: number; prihranek_eur: number;
  spodbuda_poziv: number; spodbuda_izbrana: number; spodbuda_nps: number;
  doba: [number | null, number | null, number | null];   // brez / izbrana spodbuda / NPS; null = se ne povrne
  formula: string;
  moc_kw?: number; moc_brez_ovoja_kw?: number; strosek_brez_ovoja?: number;
}

const blok = (v: Vhod) => v.tip === 'blok';
const qhnd = (D: any, v: Vhod) => (blok(v) ? D.bloki.qhnd_kwh_m2 : D.model.qhnd_kwh_m2)[v.obdobje];
const uk = (D: any, v: Vhod, u: Ukrep) => (blok(v) ? D.bloki.ukrepi : D.ukrepi)[u];

export function cena(D: any, e: Energent, n: Nastavitve, v?: Vhod): number {
  const c = v && blok(v) && D.bloki.cene_energentov_eur_kwh[e] != null ? D.bloki.cene_energentov_eur_kwh[e] : D.cene_energentov_eur_kwh[e];
  return c * (e === 'elektrika' ? n.cena_el : n.cena_en);
}

/** Stanje ovoja po izbranih ukrepih (za SCOP in izbiro črpalke). */
export function stanjePo(stanje: Stanje, ukrepi: Ukrep[]): Stanje {
  const fas = ukrepi.includes('fasada'), str = ukrepi.includes('streha') || ukrepi.includes('plosca_podstrehe');
  if (fas && str && ukrepi.includes('okna')) return 'celovita';
  if (fas && str) return stanje === 'izoliran' ? 'celovita' : 'izoliran';
  if (fas || str || ukrepi.includes('okna')) return stanje === 'neizoliran' ? 'delno' : stanje === 'delno' ? 'izoliran' : stanje;
  return stanje;
}

/** Potrebna toplota za ogrevanje Q [kWh/leto]: iz vnesene rabe ali iz tabele Qh,nd (obdobje × ovoj). */
export function potrebnaToplota(D: any, v: Vhod, stanje: Stanje = v.stanje): number {
  const q = qhnd(D, v);
  if (v.raba_kwh) return v.raba_kwh * D.model.izkoristek_kotla[v.energent] * q[stanje] / q[v.stanje];
  return v.povrsina * q[stanje];
}

/** Fizikalni prihranek toplote ukrepa na ovoju [kWh/leto], pred umeritvijo. */
export function prihranekToploteOvoja(D: any, u: Ukrep, v: Vhod): number {
  const p = uk(D, v, u);
  if (!p || p.u_pred == null) return 0;
  return v.povrsina * p.povrsina_na_m2_tlorisa * (p.u_pred - p.u_po) * D.model.kKh_ucinkoviti * D.model.faktor_prihranka_po_stanju_ovoja[v.stanje];
}

/** Umeritveni faktor: celovita prenova ovoja (fasada, streha ali plošča, okna) prihrani največ razliko do stanja »celovita«. */
export function umeritevOvoja(D: any, v: Vhod): number {
  const ph = (u: Ukrep) => prihranekToploteOvoja(D, u, v);
  const vsi = ph('fasada') + ph('okna') + (blok(v) ? ph('streha') : Math.max(ph('streha'), ph('plosca_podstrehe')));
  const meja = potrebnaToplota(D, v) - potrebnaToplota(D, v, 'celovita');
  return vsi > 0 ? Math.max(0, Math.min(1, meja / vsi)) : 0;
}

export function strosekUkrepa(D: any, u: Ukrep, v: Vhod, n: Nastavitve, moc?: number): number {
  const lastni = v.stroski?.[u];
  if (lastni) return lastni;
  let c: number;
  if (blok(v)) c = v.povrsina * D.bloki.ukrepi[u].strosek_eur_m2_stanovanja;
  else if (OVOJ.includes(u)) c = v.povrsina * D.ukrepi[u].povrsina_na_m2_tlorisa * D.ukrepi[u].strosek_eur_m2;
  else if (u === 'pv') c = (v.pv_kw || 5) * D.ukrepi.soncna_elektrarna.strosek_eur_kw;
  else if (u === 'prezracevanje') c = D.ukrepi[`prezracevanje_${v.prezracevanje || 'lokalno'}`].strosek_eur;
  else c = (moc ?? 10) * D.ukrepi[`tc_${v.tc_vrsta || 'zrak_voda'}`].strosek_eur_kw;
  return c * n.strosek;
}

/** Dodatek po predlogu NPS (ukrep N1): +20 pri F in G ali med 43 % najslabših, +10 pri E; brez podatka ocena iz obdobja in ovoja. */
export function bonusNPS(D: any, v: Vhod): number {
  const B = D.spodbude.predlog_NPS_N1;
  if (v.razred || v.nad43 != null) {
    if (v.nad43 || v.razred === 'F' || v.razred === 'G') return B.bonus_razred_F_G;
    return v.razred === 'E' ? B.bonus_razred_E : 0;
  }
  if (v.obdobje === 'pred_1980' && v.stanje === 'neizoliran') return B.bonus_razred_F_G;
  if ((v.obdobje === 'pred_1980' && v.stanje === 'delno') || (!blok(v) && v.obdobje === '1981_2002' && v.stanje === 'neizoliran')) return B.bonus_razred_E;
  return 0;
}

/** Celovita prenova po N1 (+10): hiša – fasada, streha ali plošča ter toplotna črpalka ali okna; blok – fasada, streha in okna. */
export const celovita = (v: Vhod) => blok(v)
  ? (['fasada', 'streha', 'okna'] as Ukrep[]).every((u) => v.ukrepi.includes(u))
  : v.ukrepi.includes('fasada') && (v.ukrepi.includes('streha') || v.ukrepi.includes('plosca_podstrehe')) && (v.ukrepi.includes('tc') || v.ukrepi.includes('okna'));

/** Pravilo poziva za ukrep: delež, zgornja meja v € in delitelj za znesek brez DDV. */
function pravilo(D: any, u: Ukrep, v: Vhod): { delez: number; cap: number; brezDdv: number } {
  if (blok(v)) {
    const S = D.bloki.spodbude, U = D.bloki.ukrepi;
    if (u === 'fasada' || u === 'streha') { const r = S['poziv_2025_124SUB-OBPO25_skupni_deli'][u]; return { delez: r.delez, cap: r.najvec_eur_m2 * v.povrsina * U[u].povrsina_na_m2_tlorisa, brezDdv: r.brez_ddv }; }
    if (u === 'okna') { const r = S['poziv_2026_126SUB-OB26_stanovanje'].okna; return { delez: r.delez, cap: r.najvec_eur_m2 * v.povrsina * U.okna.povrsina_na_m2_tlorisa, brezDdv: 1 }; }
    const r = S['poziv_2026_126SUB-OB26_stanovanje'].prezracevanje;
    return { delez: r.delez, cap: r.najvec_eur_naprava * Math.max(1, Math.round(v.povrsina * U.prezracevanje.naprav_na_m2)), brezDdv: 1 };
  }
  const P = D.spodbude['poziv_2026_126SUB-OB26'];
  const key = OVOJ.includes(u) && u !== 'okna' ? 'ovoj' : u === 'tc' ? `tc_${v.tc_vrsta || 'zrak_voda'}` : u;
  const pr = P[key];
  let cap = Infinity;
  if (pr.najvec_eur_m2) cap = pr.najvec_eur_m2 * v.povrsina * D.ukrepi[u].povrsina_na_m2_tlorisa;
  if (pr.najvec_eur) cap = pr.najvec_eur;
  return { delez: pr.delez, cap, brezDdv: 1 };
}

/** Spodbuda [€] po pozivu (delez = null) ali z drugim deležem (zgornje meje se povečajo sorazmerno z deležem). */
export function spodbuda(D: any, u: Ukrep, strosek: number, v: Vhod, delez: number | null = null): number {
  const p = pravilo(D, u, v);
  const d = delez ?? p.delez;
  return Math.min((strosek / p.brezDdv) * d, p.cap * (d / p.delez));
}

export function deleziNPS(D: any, u: Ukrep, v: Vhod): number {
  const B = D.spodbude.predlog_NPS_N1;
  return Math.min(B.najvec, pravilo(D, u, v).delez + bonusNPS(D, v) + (celovita(v) ? B.bonus_celovita : 0));
}

export const povracilo = (strosek: number, spodb: number, prihranek: number): number | null =>
  prihranek > 0 ? (strosek - spodb) / prihranek : null;

/** Moč toplotne črpalke [kW] = Q / 1.800 h, zaokroženo navzgor na 2 kW (najmanj 4 kW). */
export const mocTC = (D: any, Q: number) => Math.max(4, Math.ceil(Q / D.model.ure_h_polna_obremenitev / 2) * 2);

function scop(D: any, stanje: Stanje, v: Vhod) {
  return D.model.scop[stanje] + (v.tc_vrsta === 'zemlja_voda' ? D.model.scop.zemlja_voda_dodatek : 0);
}

/** Rezultat za vsak izbrani ukrep (ovoj pred toplotno črpalko) in za paket. */
export function izracun(D: any, v: Vhod, n: Nastavitve = PRIVZETO): any {
  if (blok(v)) v = { ...v, ukrepi: v.ukrepi.filter((u) => UKREPI_BLOK.includes(u)) };
  const eta = D.model.izkoristek_kotla[v.energent];
  const pEn = cena(D, v.energent, n, v), pEl = cena(D, 'elektrika', n, v);
  const Q0 = potrebnaToplota(D, v), Qcel = Math.min(Q0, potrebnaToplota(D, v, 'celovita'));
  const k = umeritevOvoja(D, v);
  const ovoj = OVOJ.filter((u) => v.ukrepi.includes(u));
  const out: Rezultat[] = [];
  const row = (u: Ukrep, ime: string, strosek: number, kwh: number, eur: number, life: number, formula: string, extra: Partial<Rezultat> = {}) => {
    const sp = spodbuda(D, u, strosek, v), si = n.spodbuda == null ? sp : spodbuda(D, u, strosek, v, n.spodbuda), sn = spodbuda(D, u, strosek, v, deleziNPS(D, u, v));
    out.push({ ukrep: u, ime, strosek, zivljenjska_doba: life, prihranek_kwh: kwh, prihranek_eur: eur, spodbuda_poziv: sp, spodbuda_izbrana: si, spodbuda_nps: sn,
      doba: [povracilo(strosek, 0, eur), povracilo(strosek, si, eur), povracilo(strosek, sn, eur)], formula, ...extra });
  };
  let dQ = 0;
  for (const u of ovoj) {
    const p = uk(D, v, u);
    const fiz = prihranekToploteOvoja(D, u, v);
    const dq = Math.min(fiz * k, Math.max(0, Q0 - Qcel - dQ));
    dQ += dq;
    const kwh = dq / eta, eur = kwh * pEn, c = strosekUkrepa(D, u, v, n);
    const A = v.povrsina * p.povrsina_na_m2_tlorisa, f = D.model.faktor_prihranka_po_stanju_ovoja[v.stanje];
    row(u, p.ime, c, kwh, eur, p.zivljenjska_doba,
      `${Math.round(A)} m² × (${p.u_pred} − ${p.u_po}) W/(m²K) × ${D.model.kKh_ucinkoviti} kKh${f < 1 ? ` × ${f} (ovoj že ${v.stanje === 'delno' ? 'delno ' : ''}izoliran)` : ''} = ${Math.round(fiz)} kWh; × ${k.toFixed(2)} (umeritev na dejansko rabo: vsi ukrepi na ovoju skupaj največ ${Math.round(Q0 - Qcel)} kWh) = ${Math.round(dq)} kWh toplote; ÷ izkoristek ${eta} × ${pEn.toFixed(3)} €/kWh`);
  }
  if (v.ukrepi.includes('prezracevanje')) {
    const p = blok(v) ? D.bloki.ukrepi.prezracevanje : D.ukrepi[`prezracevanje_${v.prezracevanje || 'lokalno'}`];
    const kwh = blok(v) ? p.prihranek_kwh_m2 * v.povrsina : p.prihranek_kwh, eur = kwh * pEn;
    row('prezracevanje', p.ime, strosekUkrepa(D, 'prezracevanje', v, n), kwh, eur, p.zivljenjska_doba, `${Math.round(kwh)} kWh na leto (Eko sklad) × ${pEn.toFixed(3)} €/kWh`);
  }
  const st1 = stanjePo(v.stanje, v.ukrepi);
  const Q1 = Math.max(Q0 - dQ, Qcel);
  if (!blok(v) && v.ukrepi.includes('tc')) {
    const p = D.ukrepi[`tc_${v.tc_vrsta || 'zrak_voda'}`];
    const st = ovoj.length ? st1 : v.stanje;
    const moc = mocTC(D, Q1), moc0 = mocTC(D, Q0);
    const staro = (Q1 / eta) * pEn, novo = (Q1 / scop(D, st, v)) * pEl, eur = staro - novo;
    const c = strosekUkrepa(D, 'tc', v, n, moc), c0 = strosekUkrepa(D, 'tc', v, n, moc0);
    row('tc', p.ime, c, Q1 / eta - Q1 / scop(D, st, v), eur, p.zivljenjska_doba,
      `toplota ${Math.round(Q1)} kWh${ovoj.length ? ' (po ukrepih na ovoju)' : ''}: danes ${Math.round(Q1)} ÷ ${eta} × ${pEn.toFixed(3)} € = ${Math.round(staro)} €, s črpalko ${Math.round(Q1)} ÷ SCOP ${scop(D, st, v).toFixed(1)} × ${pEl.toFixed(3)} € = ${Math.round(novo)} €; moč ${moc} kW`,
      { moc_kw: moc, moc_brez_ovoja_kw: moc0, strosek_brez_ovoja: c0 });
  }
  // paket: ena vsota (ovoj zmanjša prihranek črpalke in obratno), brez seštevanja povračilnih dob
  const staro = (Q0 / eta) * pEn;
  const vent = out.find((r) => r.ukrep === 'prezracevanje')?.prihranek_kwh ?? 0;
  const tc = !blok(v) && v.ukrepi.includes('tc');
  const novo = tc ? (Math.max(0, Q1 - vent * eta) / scop(D, st1, v)) * pEl : (Math.max(0, Q1 - vent * eta) / eta) * pEn;
  const paket: any = {
    strosek: out.reduce((s, r) => s + r.strosek, 0),
    spodbuda: out.reduce((s, r) => s + r.spodbuda_izbrana, 0),
    spodbuda_nps: out.reduce((s, r) => s + r.spodbuda_nps, 0),
    prihranek_eur: staro - novo,
    stroski_danes: staro,
  };
  paket.doba = [povracilo(paket.strosek, 0, paket.prihranek_eur), povracilo(paket.strosek, paket.spodbuda, paket.prihranek_eur), povracilo(paket.strosek, paket.spodbuda_nps, paket.prihranek_eur)];
  // isti paket brez ukrepov, ki se s spodbudo v življenjski dobi ne povrnejo (npr. okna)
  const ne = out.filter((r) => r.doba[1] == null || r.doba[1] > r.zivljenjska_doba).map((r) => r.ukrep);
  if (ne.length && ne.length < out.length) {
    const r2 = izracun(D, { ...v, ukrepi: v.ukrepi.filter((u) => !ne.includes(u)) }, n);
    paket.brez = { ukrepi: ne, doba: r2.paket.doba, strosek: r2.paket.strosek, prihranek_eur: r2.paket.prihranek_eur };
  }
  const Qnet = Math.max(0, Q1 - vent * eta);
  const el_ogrevanje = tc ? Qnet / scop(D, st1, v) : v.energent === 'elektrika' ? Qnet / eta : 0;
  const pv = !blok(v) && v.ukrepi.includes('pv') ? soncna(D, v, n, el_ogrevanje) : null;
  return { Q0: Math.round(Q0), Q1: Math.round(Q1), Qnet, el_ogrevanje, stanje_po: st1, umeritev: k, rezultati: out, paket, pv, bonus: bonusNPS(D, v), celovita: celovita(v) };
}

const HDD = (D: any): number[] => D.model.hdd_delez_mesec;
const PROF = (D: any): number[] => { const p = D.ukrepi.soncna_elektrarna.profil_gospodinjstva_mesec; const s = p.reduce((a: number, b: number) => a + b, 0); return p.map((x: number) => x / s); };
const vsota = (a: number[]) => a.reduce((x, y) => x + y, 0);

/** Privzeta moč elektrarne [kW]: letna proizvodnja ≈ letna raba elektrike (gospodinjstvo in ogrevanje), 3–15 kW. */
export function privzetaMocPV(D: any, el_ogrevanje: number, raba_gosp?: number | null): number {
  const E = (raba_gosp || D.ukrepi.soncna_elektrarna.raba_gospodinjstva_kwh) + el_ogrevanje;
  return Math.min(15, Math.max(3, Math.round(E / vsota(D.ukrepi.soncna_elektrarna.proizvodnja_kwh_kw_mesec))));
}

/** Sončna elektrarna: mesečna proizvodnja in raba, prihranek in povračilna doba za tri načine obračuna.
 *  Letni net metering: pokrita je letna raba, letni presežek ni plačan. Nova shema: sproti porabljeni delež proizvodnje (brez hranilnika)
 *  zmanjša nakup in omrežnino za energijo, vsa oddana elektrika se proda po odkupni ceni. Mesečni net metering (hipotetično): pokrita je
 *  raba v istem mesecu, mesečni presežek po odkupni ceni. Pokrita kWh je vredna kot kupljena elektrika (energija, omrežnina za energijo,
 *  prispevki, DDV); omrežnina za moč in druge fiksne postavke se ne spremenijo. */
export function soncna(D: any, v: Vhod, n: Nastavitve, el_ogrevanje: number) {
  const S = D.ukrepi.soncna_elektrarna;
  const kw = v.pv_kw || privzetaMocPV(D, el_ogrevanje, v.raba_gosp_kwh);
  const gosp = v.raba_gosp_kwh || S.raba_gospodinjstva_kwh;
  const P: number[] = S.proizvodnja_kwh_kw_mesec.map((x: number) => x * kw);
  const prof = PROF(D), hdd = HDD(D);
  const C = prof.map((p, m) => gosp * p + el_ogrevanje * hdd[m]);
  const pEl = cena(D, 'elektrika', n), odk = n.odkup ?? S.odkupna_cena_eur_kwh;
  const Py = vsota(P), Cy = vsota(C);
  const pokrito: Record<Obracun, number> = {
    letni: Math.min(Py, Cy),
    nova: vsota(P.map((p, m) => Math.min(p * S.delez_sproti, C[m]))),
    mesecni: vsota(P.map((p, m) => Math.min(p, C[m]))),
  };
  const strosek = v.stroski?.pv || kw * S.strosek_eur_kw * n.strosek;
  const rezimi = Object.fromEntries(OBRACUNI.map((o) => {
    const prodano = o === 'letni' ? 0 : Py - pokrito[o];
    const eur = pokrito[o] * pEl + prodano * odk;
    return [o, { pokrito_kwh: pokrito[o], prodano_kwh: prodano, neplacano_kwh: Py - pokrito[o] - prodano, prihranek_eur: eur, doba: povracilo(strosek, 0, eur) }];
  })) as Record<Obracun, { pokrito_kwh: number; prodano_kwh: number; neplacano_kwh: number; prihranek_eur: number; doba: number | null }>;
  const zima = [11, 0, 1];
  const pokritost_zima = vsota(zima.map((m) => Math.min(P[m], C[m]))) / vsota(zima.map((m) => C[m]));
  return { kw, strosek, zivljenjska_doba: S.zivljenjska_doba as number, proizvodnja: P, raba: C, proizvodnja_kwh: Py, raba_kwh: Cy, rezimi, pokritost_zima, pEl, odkup: odk as number };
}

/** Primarna energija po modelu kalkulatorja [kWh/leto] brez elektrarne in mesečna elektrika za stavbo. */
function primarnaModel(D: any, v: Vhod, r: any) {
  const M = D.model, A = v.povrsina, fp = M.fp;
  const tc = v.ukrepi.includes('tc');
  const dhw = M.topla_voda_kwh_m2 * A, aux = M.pomozna_el_kwh_m2 * A, hdd = HDD(D);
  let pe: number, elM: number[];
  if (tc) {
    const s = scop(D, r.stanje_po, v), el = (r.Qnet + dhw) / s;
    pe = el * fp.elektrika + (r.Qnet + dhw - el) * fp.okolica + aux * fp.elektrika;
    elM = hdd.map((h) => (r.Qnet / s) * h + (dhw / s + aux) / 12);
  } else {
    const eta = M.izkoristek_kotla[v.energent];
    pe = ((r.Qnet + dhw) / eta) * fp[v.energent] + aux * fp.elektrika;
    elM = hdd.map((h) => (v.energent === 'elektrika' ? r.Qnet * h + dhw / 12 : 0) + aux / 12);
  }
  return { pe, elM };
}

const VIR_IZK: Record<string, string> = { kurilno_olje: 'olje', zemeljski_plin: 'plin', polena: 'les', peleti: 'les', daljinska_toplota: 'daljinsko' };
/** Umeritev ocene na izkaznice: mediana primarne energije neprenovljenih hiš (obdobje × ogrevanje) ÷ ocena modela za neizolirano hišo. */
export function umeritevPE(D: any, v: Vhod): number {
  const R = (blok(v) ? D.bloki : D.model).pe_izkaznice_neprenovljene?.[v.obdobje];
  if (!R) return 1;
  const vals = Object.values(R) as number[];
  const ref = R[VIR_IZK[v.energent]] ?? vals.reduce((a, b) => a + b, 0) / vals.length;
  const v0: Vhod = { ...v, stanje: 'neizoliran', ukrepi: [], raba_kwh: null };
  const m = primarnaModel(D, v0, izracun(D, v0)).pe / v.povrsina;
  return Math.min(2, Math.max(0.7, ref / m));
}

/** Ocena skupne primarne energije [kWh/(m²·a)] za ogrevanje, toplo vodo in pomožno elektriko po izbranih ukrepih (r = izracun),
 *  umerjena na izkaznice neprenovljenih hiš (umeritev se s stanjem ovoja zmanjšuje in po celoviti prenovi izgine); elektrarna jo zmanjša
 *  za elektriko stavbe v mesecu, ko jo proizvede (mesečna bilanca). Pogoji za brezemisijsko stavbo (ZEB): pod mejo razreda A,
 *  brez fosilnih goriv v stavbi, izoliran ovoj (fasada in streha ali plošča). */
export function primarna(D: any, v: Vhod, r: any) {
  const M = D.model, A = v.povrsina, fp = M.fp, tc = v.ukrepi.includes('tc');
  const { pe: pe0, elM } = primarnaModel(D, v, r);
  const w = ({ neizoliran: 1, delno: 1, izoliran: 0, celovita: 0 } as Record<Stanje, number>)[r.stanje_po as Stanje];
  let pe = pe0 * (1 + (umeritevPE(D, v) - 1) * w);
  const pvKwh = r.pv ? vsota(r.pv.proizvodnja.map((p: number, m: number) => Math.min(p, elM[m]))) : 0;
  pe -= pvKwh * fp.elektrika;
  const pe_m2 = pe / A;
  const fosil = !tc && ['kurilno_olje', 'zemeljski_plin'].includes(v.energent);
  const ovoj = r.stanje_po === 'izoliran' || r.stanje_po === 'celovita';
  return { pe_m2, meja: M.zeb_meja_pe_kwh_m2 as number, fosil, ovoj, zeb: pe_m2 <= M.zeb_meja_pe_kwh_m2 && !fosil && ovoj, pv_za_stavbo_kwh: pvKwh };
}

const ENERGENT_TOZ: Record<string, string> = { kurilno_olje: 'kurilno olje', zemeljski_plin: 'zemeljski plin', peleti: 'pelete', polena: 'polena', daljinska_toplota: 'daljinsko toploto', elektrika: 'elektriko' };
const evro = (x: number) => `${(Math.round(x / 100) * 100).toLocaleString('sl-SI', { useGrouping: 'always' } as Intl.NumberFormatOptions)} €`;

/** Opozorila »najprej učinkovita raba energije, nato obnovljivi viri«: toplotna črpalka ali elektrarna na neizolirani hiši brez
 *  ukrepa na ovoju (fasada, streha ali plošča). */
export function opozorila(D: any, v: Vhod, n: Nastavitve, r: any) {
  const out: { tip: 'tc' | 'pv' | 'najslabse'; besedilo: string }[] = [];
  if (blok(v) || v.stanje === 'izoliran' || OVOJ.some((u) => u !== 'okna' && v.ukrepi.includes(u))) return out;
  const tc = v.ukrepi.includes('tc'), pv = v.ukrepi.includes('pv');
  if (!tc && !pv) return out;
  if (tc) {
    const z = izracun(D, { ...v, ukrepi: [...v.ukrepi, 'fasada', 'plosca_podstrehe'] }, n);
    const a = r.rezultati.find((x: Rezultat) => x.ukrep === 'tc'), b = z.rezultati.find((x: Rezultat) => x.ukrep === 'tc');
    const kwh = Math.round((r.el_ogrevanje - z.el_ogrevanje) / 100) * 100;
    out.push({ tip: 'tc', besedilo: `Toplotna črpalka za ${v.stanje === 'delno' ? 'delno izolirano' : 'neizolirano'} hišo potrebuje okoli ${a.moc_kw} kW. Če bi prej izolirali fasado in strop proti podstrešju, bi zadostovala črpalka za ${b.moc_kw} kW, ki je okoli ${evro(a.strosek - b.strosek)} cenejša in porabi okoli ${kwh.toLocaleString('sl-SI', { useGrouping: 'always' } as Intl.NumberFormatOptions)} kWh elektrike na leto manj. Če ovoj izolirate pozneje, bo črpalka prevelika in bo delala manj učinkovito.` });
  }
  if (pv && r.pv) {
    out.push({ tip: 'pv', besedilo: r.el_ogrevanje > 0
      ? `Elektrarna proizvede največ poleti, ko hiša ne potrebuje ogrevanja: od decembra do februarja pokrije le okoli ${Math.round(r.pv.pokritost_zima * 100)} % elektrike, ki jo takrat porabite. Toplota, ki je zaradi izolacije ne potrebujete, pozimi prihrani več kot elektrarna.`
      : `Elektrarna ne zmanjša stroškov ogrevanja na ${ENERGENT_TOZ[v.energent]}, ki so največji strošek neizolirane hiše. Najprej zmanjšajte potrebo po toploti, nato zamenjajte ogrevanje, na koncu dodajte elektrarno.` });
  }
  if (bonusNPS(D, v) >= D.spodbude.predlog_NPS_N1.bonus_razred_F_G)
    out.push({ tip: 'najslabse', besedilo: 'Vaša hiša je verjetno med 43 % energetsko najmanj učinkovitih stavb. Po načelu »energetska učinkovitost na prvem mestu« naj bo prvi korak izolacija ovoja; predlog NPS 2050 za take stavbe predvideva višjo spodbudo (+20 odstotnih točk) in še +10 za celovito prenovo.' });
  return out;
}

export interface Korak { ukrep: Ukrep; leto: number }

/** Priporočen vrstni red (leto): ovoj najprej, okna in prezračevanje, nato toplotna črpalka, na koncu elektrarna. */
export const PRIPOROCEN: Record<Ukrep, number> = { fasada: 0, streha: 0, plosca_podstrehe: 0, okna: 2, prezracevanje: 2, tc: 3, pv: 4 };

/** Prenova po korakih: ukrepi v različnih letih. Kumulativni stroški (naložbe po odbitku spodbude + energija za ogrevanje in elektriko
 *  gospodinjstva − vrednost elektrike iz elektrarne) za načrt in brez prenove; ukrep, ki se izteče pred koncem obdobja (toplotna črpalka
 *  po 18 letih), se zamenja, preostala vrednost ukrepov ob koncu obdobja se odšteje v zadnjem letu. Spodbuda NPS za načrt po izkazu o prenovi: +10 za vse
 *  korake, če se konča s celovito prenovo, sicer +5 za korak; vse naenkrat brez dodatka za korak. */
export function nacrt(D: any, v: Vhod, n: Nastavitve, koraki: Korak[], obracun: Obracun = 'nova', let_ = 20) {
  const B = D.spodbude.predlog_NPS_N1;
  const vse = koraki.map((k) => k.ukrep);
  const cel = celovita({ ...v, ukrepi: vse });
  const pEl = cena(D, 'elektrika', n), gosp = (v.raba_gosp_kwh || D.ukrepi.soncna_elektrarna.raba_gospodinjstva_kwh) * pEl;
  const naenkrat = new Set(koraki.map((k) => k.leto)).size <= 1;
  const bonusKorak = cel ? B.bonus_celovita : naenkrat ? 0 : B.bonus_korak_izkaz;
  const npsDelez = (u: Ukrep) => Math.min(B.najvec, pravilo(D, u, v).delez + bonusNPS(D, v) + bonusKorak);
  // stroški energije v letu y: današnje cene × (1 + rast)^y, za kurilno olje in plin od uvedbe ETS2 še cena CO₂ (z DDV)
  const M = D.model, E2 = M.ets2, g = n.rast ?? M.rast_cen_energije, co2 = n.ets2 ?? E2.cena_eur_t;
  const ef = E2.emisije_kg_kwh[v.energent] ?? 0, pEn = cena(D, v.energent, n, v);
  const stanje = (inst: Ukrep[]) => {
    const r = izracun(D, { ...v, ukrepi: inst }, n);
    const ogr = r.paket.stroski_danes - r.paket.prihranek_eur;
    const gorivo = !inst.includes('tc') && ef ? ogr / pEn : 0;   // kWh kurilnega olja ali plina na leto
    return { r, gorivo, energija: ogr + gosp - (r.pv ? r.pv.rezimi[obracun].prihranek_eur : 0) };
  };
  const vLetu = (s: { energija: number; gorivo: number }, y: number) =>
    (s.energija + (M.zacetno_leto + y >= E2.od_leta ? s.gorivo * ef * co2 / 1000 * E2.ddv : 0)) * (1 + g) ** y;
  const s0 = stanje([]);
  const brez = [0];
  for (let y = 0; y < let_; y++) brez.push(Math.round(brez[y] + vLetu(s0, y)));
  const dogodki: any[] = [];
  const serija = { poziv: [0], nps: [0] };
  let inst: Ukrep[] = [], kp = 0, kn = 0, cur = s0;
  // vgrajeni ukrepi: leto (zadnje) vgradnje, neto strošek in življenjska doba – za zamenjave in preostalo vrednost
  const vgr: { ukrep: Ukrep; leto: number; netP: number; netN: number; zd: number }[] = [];
  for (let y = 0; y < let_; y++) {
    for (const g of vgr.filter((x) => x.leto + x.zd === y)) {
      // zamenjava po izteku življenjske dobe (črpalka po stanju ovoja v tem letu)
      const row = g.ukrep === 'pv' ? null : cur.r.rezultati.find((x: Rezultat) => x.ukrep === g.ukrep);
      const c = row ? row.strosek : cur.r.pv.strosek;
      const sp = row ? (n.spodbuda == null ? spodbuda(D, g.ukrep, c, v) : spodbuda(D, g.ukrep, c, v, n.spodbuda)) : 0;
      const sn = row ? spodbuda(D, g.ukrep, c, v, Math.min(B.najvec, pravilo(D, g.ukrep, v).delez + bonusNPS(D, v))) : 0;
      kp += c - sp; kn += c - sn;
      Object.assign(g, { leto: y, netP: c - sp, netN: c - sn });
      dogodki.push({ leto: y, ukrep: g.ukrep, ime: `Zamenjava: ${(row ? row.ime : 'sončna elektrarna').toLowerCase()}${row?.moc_kw ? ` ${row.moc_kw} kW` : ''}`, strosek: c, spodbuda: sp, spodbuda_nps: sn,
        moc: row?.moc_kw, zamenjava: true, toplota_m2: cur.r.Q1 / v.povrsina, pe_m2: primarna(D, { ...v, ukrepi: inst }, cur.r).pe_m2, energija: cur.energija });
    }
    const nova = koraki.filter((k) => k.leto === y).map((k) => k.ukrep);
    if (nova.length) {
      inst = [...inst, ...nova];
      cur = stanje(inst);
      const pe = primarna(D, { ...v, ukrepi: inst }, cur.r);
      for (const u of nova) {
        let c: number, sp = 0, sn = 0, moc: number | undefined, ime: string, zd: number;
        if (u === 'pv') { c = cur.r.pv.strosek; ime = `Sončna elektrarna ${cur.r.pv.kw} kW`; zd = cur.r.pv.zivljenjska_doba; }
        else {
          const row = cur.r.rezultati.find((x: Rezultat) => x.ukrep === u);
          c = row.strosek; moc = row.moc_kw; ime = row.ime + (moc ? ` ${moc} kW` : ''); zd = row.zivljenjska_doba;
          sp = n.spodbuda == null ? spodbuda(D, u, c, v) : spodbuda(D, u, c, v, n.spodbuda);
          sn = spodbuda(D, u, c, v, npsDelez(u));
        }
        kp += c - sp; kn += c - sn;
        vgr.push({ ukrep: u, leto: y, netP: c - sp, netN: c - sn, zd });
        dogodki.push({ leto: y, ukrep: u, ime, strosek: c, spodbuda: sp, spodbuda_nps: sn, moc, toplota_m2: cur.r.Q1 / v.povrsina, pe_m2: pe.pe_m2, energija: cur.energija });
      }
    }
    const e = vLetu(cur, y);
    kp += e; kn += e;
    serija.poziv.push(Math.round(kp)); serija.nps.push(Math.round(kn));
  }
  // preostala vrednost ukrepov ob koncu obdobja (linearno po življenjski dobi): serija so izdatki, skupaj = izdatki − preostala vrednost
  const ost = (k: 'netP' | 'netN') => vsota(vgr.map((g) => g[k] * Math.max(0, g.zd - (let_ - g.leto)) / g.zd));
  const ostanek = { poziv: ost('netP'), nps: ost('netN') };
  const konec = primarna(D, { ...v, ukrepi: inst }, cur.r), zacetek = primarna(D, { ...v, ukrepi: [] }, s0.r);
  // črpalka, vgrajena pred zadnjim ukrepom na ovoju, je na koncu prevelika
  const tcK = koraki.find((k) => k.ukrep === 'tc');
  const prvi = dogodki.filter((d) => !d.zamenjava);
  const zadnjiOvoj = Math.max(-1, ...koraki.filter((k) => OVOJ.includes(k.ukrep)).map((k) => k.leto));
  const tcKonec = cur.r.rezultati.find((x: Rezultat) => x.ukrep === 'tc'), tcDog = prvi.find((d) => d.ukrep === 'tc');
  const prevelika = tcK && tcDog && tcKonec && tcK.leto < zadnjiOvoj && tcDog.moc > tcKonec.moc_kw ? { moc: tcDog.moc as number, moc_konec: tcKonec.moc_kw as number } : null;
  return {
    dogodki, serija, brez, ostanek, izdatki: { poziv: serija.poziv.at(-1)!, nps: serija.nps.at(-1)! },
    skupaj: { poziv: Math.round(serija.poziv.at(-1)! - ostanek.poziv), nps: Math.round(serija.nps.at(-1)! - ostanek.nps), brez: brez.at(-1)! }, celovita: cel, naenkrat, bonus_korak: bonusKorak,
    spodbuda: { poziv: vsota(prvi.map((d) => d.spodbuda)), nps: vsota(prvi.map((d) => d.spodbuda_nps)) },
    nalozbe: vsota(prvi.map((d) => d.strosek)), zamenjave: dogodki.filter((d) => d.zamenjava), energija_zacetek: s0.energija, energija_konec: cur.energija, zacetek, konec, prevelika,
  };
}


export const zaokrozi = (x: number) => Math.round(x * 10) / 10;

/** Zgodba »Dve hiši, ista ulica«: kumulativni stroški (naložbe po odbitku spodbude po pozivu 2026 + energija) po letih za vsak
 *  vrstni red ukrepov in za hišo brez prenove. Stroški kot v kalkulatorju (strosekUkrepa: priznani stroški Eko sklada), črpalka po moči ob vgradnji. */
export function dveHisi(D: any, S: any) {
  const v0: Vhod = { ...S.hisa, ukrepi: [] };
  const pEn = D.cene_energentov_eur_kwh[v0.energent], pEl = D.cene_energentov_eur_kwh.elektrika, eta = D.model.izkoristek_kotla[v0.energent];
  const brez = Array.from({ length: S.let + 1 }, (_, y) => Math.round((y * potrebnaToplota(D, v0) / eta) * pEn));
  const scen = S.scenariji.map((sc: any) => {
    let stanje: Stanje = v0.stanje, moc: number | null = null, kum = 0, el = 0, nalozbe = 0, spodbude = 0;
    const serija = [0], dogodki: { leto: number; ukrep: string; strosek: number; spodbuda: number; moc?: number }[] = [];
    for (let y = 0; y < S.let; y++) {
      for (const k of sc.koraki.filter((x: any) => x.leto === y)) {
        let c: number, sp: number;
        if (k.ukrep === 'tc') {
          moc = mocTC(D, potrebnaToplota(D, v0, stanje));
          c = strosekUkrepa(D, 'tc', v0, { strosek: 1 } as Nastavitve, moc); sp = spodbuda(D, 'tc', c, v0);
        } else {
          c = strosekUkrepa(D, k.ukrep, v0, { strosek: 1 } as Nastavitve); sp = spodbuda(D, k.ukrep, c, v0);
          stanje = stanjePo(stanje, [k.ukrep]);
        }
        nalozbe += c; spodbude += sp; kum += c - sp;
        dogodki.push({ leto: y, ukrep: k.ukrep, strosek: c, spodbuda: sp, ...(k.ukrep === 'tc' ? { moc: moc! } : {}) });
      }
      const Q = potrebnaToplota(D, v0, stanje);
      if (moc) { const e = Q / D.model.scop[stanje]; el += e; kum += e * pEl; } else kum += (Q / eta) * pEn;
      serija.push(Math.round(kum));
    }
    return { id: sc.id, ime: sc.ime, serija, dogodki, moc, nalozbe, spodbude, elektrika_kwh: Math.round(el), skupaj: Math.round(kum) };
  });
  return { brez, scenariji: scen };
}

/** Razred po primarni energiji (meje A|B … F|G za izbrano vrsto stavbe). */
export const razred = (pe: number, meje: number[]) => 'ABCDEFG'[meje.filter((b) => pe > b).length];

/** Vrstni red, pri katerem se najprej vgradijo obnovljivi viri (za primerjavo s priporočenim). */
export const OVE_PRVO: Record<Ukrep, number> = { tc: 0, pv: 1, okna: 3, prezracevanje: 3, fasada: 5, streha: 5, plosca_podstrehe: 5 };
const URE: Ukrep[] = ['fasada', 'streha', 'plosca_podstrehe', 'okna', 'prezracevanje'];

/** Izpis prenove: različice iz izbranih ukrepov – delne prenove (vsak ukrep posebej, vsi URE skupaj, vsi OVE skupaj; pri več kot štirih
 *  ukrepih je ovoj ena enota),
 *  vsi ukrepi naenkrat, po korakih najprej URE (PRIPOROCEN) in po korakih najprej OVE (OVE_PRVO). */
export function variante(D: any, v: Vhod, n: Nastavitve, obracun: Obracun = 'nova', let_ = 20) {
  const sel = v.ukrepi.filter((u) => u !== 'pv' || !blok(v));
  const ovoj = sel.filter((u) => OVOJ.includes(u));
  const enote: Ukrep[][] = sel.length > 4 && ovoj.length > 1 ? [ovoj, ...sel.filter((u) => !OVOJ.includes(u)).map((u) => [u])] : sel.map((u) => [u]);
  const vh = { ...v, ukrepi: [] as Ukrep[] };
  const run = (uk: Ukrep[], leta: (u: Ukrep) => number) => nacrt(D, vh, n, uk.map((u) => ({ ukrep: u, leto: leta(u) })), obracun, let_);
  const out: { skupina: 'delna' | 'naenkrat' | 'ure' | 'ove'; ukrepi: Ukrep[]; N: ReturnType<typeof nacrt> }[] = [];
  // delne prenove: vsak ukrep posebej ter vsi ukrepi URE skupaj in vsi OVE skupaj (preglednost namesto vseh kombinacij)
  const kljuc = (a: Ukrep[]) => [...a].sort().join('+');
  const vsi = kljuc(sel), podm: Ukrep[][] = [];
  const dodaj = (a: Ukrep[]) => { if (a.length && kljuc(a) !== vsi && !podm.some((x) => kljuc(x) === kljuc(a))) podm.push(a); };
  enote.forEach(dodaj);
  dodaj(sel.filter((u) => URE.includes(u)));
  dodaj(sel.filter((u) => !URE.includes(u)));
  for (const uk of podm) out.push({ skupina: 'delna', ukrepi: uk, N: run(uk, () => 0) });
  if (sel.length) out.push({ skupina: 'naenkrat', ukrepi: sel, N: run(sel, () => 0) });
  const imaUre = sel.some((u) => URE.includes(u)), imaOve = sel.some((u) => !URE.includes(u));
  if (sel.length > 1 && new Set(sel.map((u) => PRIPOROCEN[u])).size > 1) out.push({ skupina: 'ure', ukrepi: sel, N: run(sel, (u) => PRIPOROCEN[u]) });
  if (imaUre && imaOve) out.push({ skupina: 'ove', ukrepi: sel, N: run(sel, (u) => OVE_PRVO[u]) });
  return out;
}
