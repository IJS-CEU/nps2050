// Kalkulator »Se mi splača?« – čiste funkcije (brez DOM), enostavne nediskontirane povračilne dobe.
// Podatki: src/data/povracilne_dobe.json (Eko sklad 2023–2025, poziva 126SUB-OB26 in 124SUB-OBPO25, SURS, Agencija za energijo,
// analiza vgradenj TČ, osnutek NPS 2050). Testi: tests/povracilo.test.mjs.
//
// Hiša ali stanovanje v bloku. Prihranek ukrepa na ovoju: površina × (U_pred − U_po) × 45 kKh × faktor po stanju ovoja,
// sorazmerno zmanjšan tako, da vsi ukrepi na ovoju skupaj ne prihranijo več od razlike do stanja po celoviti prenovi (tabela Qh,nd).
// Tako se vsota prihrankov posameznih ukrepov ujema s prihrankom paketa, pri novejših in že delno izoliranih stavbah pa
// prihranek ni precenjen (dejanska raba je nižja od računske).

export type Tip = 'hisa' | 'blok';
export type Obdobje = 'pred_1980' | '1981_2002' | 'po_2002';
export type Stanje = 'neizoliran' | 'delno' | 'izoliran' | 'celovita';
export type Energent = 'kurilno_olje' | 'zemeljski_plin' | 'peleti' | 'polena' | 'elektrika' | 'daljinska_toplota';
export type Ukrep = 'fasada' | 'streha' | 'plosca_podstrehe' | 'okna' | 'prezracevanje' | 'tc';
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
}

export interface Nastavitve {
  cena_el: number;                // faktor cene elektrike (1 = privzeta)
  cena_en: number;                // faktor cene sedanjega energenta
  strosek: number;                // faktor stroška naložbe
  spodbuda: number | null;        // enoten delež spodbude (0–0,7) namesto pravil poziva; null = pravila pozivov
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
  return { Q0: Math.round(Q0), Q1: Math.round(Q1), stanje_po: st1, umeritev: k, rezultati: out, paket, bonus: bonusNPS(D, v), celovita: celovita(v) };
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
