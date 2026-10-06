// Kalkulator »Se mi splača?« – čiste funkcije (brez DOM), enostavne nediskontirane povračilne dobe.
// Podatki: src/data/povracilne_dobe.json (Eko sklad 2023–2025, poziv 126SUB-OB26, SURS, analiza vgradenj TČ, osnutek NPS 2050).
// Testi: tests/povracilo.test.mjs (referenčni rezultati za hišo 110 m² pred letom 1980 z neizoliranim ovojem).

export type Obdobje = 'pred_1980' | '1981_2002' | 'po_2002';
export type Stanje = 'neizoliran' | 'delno' | 'izoliran' | 'celovita';
export type Energent = 'kurilno_olje' | 'zemeljski_plin' | 'peleti' | 'polena' | 'elektrika' | 'daljinska_toplota';
export type Ukrep = 'fasada' | 'streha' | 'plosca_podstrehe' | 'okna' | 'prezracevanje' | 'tc';
export const OVOJ: Ukrep[] = ['fasada', 'streha', 'plosca_podstrehe', 'okna'];

export interface Vhod {
  povrsina: number;               // ogrevana površina, m²
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
  spodbuda: number | null;        // enoten delež spodbude (0–0,7) namesto pravil poziva; null = pravila poziva 2026
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

const r1 = (x: number) => Math.round(x * 10) / 10;

export function cena(D: any, e: Energent, n: Nastavitve): number {
  const c = D.cene_energentov_eur_kwh[e] as number;
  return c * (e === 'elektrika' ? n.cena_el : n.cena_en);
}

/** Stanje ovoja po izbranih ukrepih: fasada in streha ali plošča → izoliran; drug ukrep na ovoju → za stopnjo bolje. */
export function stanjePo(stanje: Stanje, ukrepi: Ukrep[]): Stanje {
  const fas = ukrepi.includes('fasada'), str = ukrepi.includes('streha') || ukrepi.includes('plosca_podstrehe');
  if (fas && str && ukrepi.includes('okna')) return 'celovita';
  if (fas && str) return stanje === 'izoliran' ? 'celovita' : 'izoliran';
  if (fas || str || ukrepi.includes('okna')) return stanje === 'neizoliran' ? 'delno' : stanje === 'delno' ? 'izoliran' : stanje;
  return stanje;
}

/** Potrebna toplota za ogrevanje Q [kWh/leto]: iz vnesene rabe ali iz tabele Qh,nd (obdobje × ovoj). */
export function potrebnaToplota(D: any, v: Vhod, stanje: Stanje = v.stanje): number {
  const q = v.povrsina * D.model.qhnd_kwh_m2[v.obdobje][stanje];
  if (v.raba_kwh && stanje === v.stanje) return v.raba_kwh * D.model.izkoristek_kotla[v.energent];
  if (v.raba_kwh) return q * (v.raba_kwh * D.model.izkoristek_kotla[v.energent]) / (v.povrsina * D.model.qhnd_kwh_m2[v.obdobje][v.stanje]);
  return q;
}

/** Prihranek toplote ukrepa na ovoju [kWh/leto] = površina × (U_pred − U_po) × 45 kKh × faktor po stanju ovoja. */
export function prihranekToploteOvoja(D: any, u: Ukrep, v: Vhod): number {
  const p = D.ukrepi[u];
  const A = v.povrsina * p.povrsina_na_m2_tlorisa;
  return A * (p.u_pred - p.u_po) * D.model.kKh_ucinkoviti * D.model.faktor_prihranka_po_stanju_ovoja[v.stanje];
}

export function strosekUkrepa(D: any, u: Ukrep, v: Vhod, n: Nastavitve, moc?: number): number {
  const lastni = v.stroski?.[u];
  if (lastni) return lastni;
  let c: number;
  if (OVOJ.includes(u)) c = v.povrsina * D.ukrepi[u].povrsina_na_m2_tlorisa * D.ukrepi[u].strosek_eur_m2;
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
  if ((v.obdobje === 'pred_1980' && v.stanje === 'delno') || (v.obdobje === '1981_2002' && v.stanje === 'neizoliran')) return B.bonus_razred_E;
  return 0;
}

/** Celovita prenova po N1 (+10): fasada, streha ali plošča in toplotna črpalka ali že izoliran ovoj. */
export const celovita = (v: Vhod) => v.ukrepi.includes('fasada') && (v.ukrepi.includes('streha') || v.ukrepi.includes('plosca_podstrehe')) && (v.ukrepi.includes('tc') || v.ukrepi.includes('okna'));

/** Spodbuda [€] po pozivu 126SUB-OB26 (delez = null) ali z drugim deležem (zgornje meje se povečajo sorazmerno). */
export function spodbuda(D: any, u: Ukrep, strosek: number, v: Vhod, delez: number | null = null): number {
  const P = D.spodbude['poziv_2026_126SUB-OB26'];
  const key = OVOJ.includes(u) && u !== 'okna' ? 'ovoj' : u === 'tc' ? `tc_${v.tc_vrsta || 'zrak_voda'}` : u;
  const pr = P[key];
  const d = delez ?? pr.delez;
  let cap = Infinity;
  if (pr.najvec_eur_m2) cap = pr.najvec_eur_m2 * v.povrsina * D.ukrepi[u].povrsina_na_m2_tlorisa;
  if (pr.najvec_eur) cap = pr.najvec_eur;
  cap *= d / pr.delez;
  return Math.min(strosek * d, cap);
}

export function deleziNPS(D: any, u: Ukrep, v: Vhod): number {
  const P = D.spodbude['poziv_2026_126SUB-OB26'], B = D.spodbude.predlog_NPS_N1;
  const key = OVOJ.includes(u) && u !== 'okna' ? 'ovoj' : u === 'tc' ? `tc_${v.tc_vrsta || 'zrak_voda'}` : u;
  return Math.min(B.najvec, P[key].delez + bonusNPS(D, v) + (celovita(v) ? B.bonus_celovita : 0));
}

export const povracilo = (strosek: number, spodb: number, prihranek: number): number | null =>
  prihranek > 0 ? (strosek - spodb) / prihranek : null;

/** Moč toplotne črpalke [kW] = Q / 1.800 h, zaokroženo navzgor na 2 kW (najmanj 4 kW). */
export const mocTC = (D: any, Q: number) => Math.max(4, Math.ceil(Q / D.model.ure_h_polna_obremenitev / 2) * 2);

function scop(D: any, stanje: Stanje, v: Vhod) {
  return D.model.scop[stanje] + (v.tc_vrsta === 'zemlja_voda' ? D.model.scop.zemlja_voda_dodatek : 0);
}

/** Rezultat za vsak izbrani ukrep (ovoj vedno pred toplotno črpalko) in za paket. */
export function izracun(D: any, v: Vhod, n: Nastavitve = PRIVZETO) {
  const eta = D.model.izkoristek_kotla[v.energent];
  const pEn = cena(D, v.energent, n), pEl = cena(D, 'elektrika', n);
  const Q0 = potrebnaToplota(D, v);
  const ovoj = OVOJ.filter((u) => v.ukrepi.includes(u));
  const out: Rezultat[] = [];
  const row = (u: Ukrep, ime: string, strosek: number, kwh: number, eur: number, life: number, formula: string, extra: Partial<Rezultat> = {}) => {
    const sp = spodbuda(D, u, strosek, v), si = n.spodbuda == null ? sp : spodbuda(D, u, strosek, v, n.spodbuda), sn = spodbuda(D, u, strosek, v, deleziNPS(D, u, v));
    out.push({ ukrep: u, ime, strosek, zivljenjska_doba: life, prihranek_kwh: kwh, prihranek_eur: eur, spodbuda_poziv: sp, spodbuda_izbrana: si, spodbuda_nps: sn,
      doba: [povracilo(strosek, 0, eur), povracilo(strosek, si, eur), povracilo(strosek, sn, eur)], formula, ...extra });
  };
  let dQ = 0;
  for (const u of ovoj) {
    const p = D.ukrepi[u];
    const dq = Math.min(prihranekToploteOvoja(D, u, v), Math.max(0, 0.8 * Q0 - dQ));
    dQ += dq;
    const kwh = dq / eta, eur = kwh * pEn, c = strosekUkrepa(D, u, v, n);
    const A = v.povrsina * p.povrsina_na_m2_tlorisa;
    row(u, p.ime, c, kwh, eur, p.zivljenjska_doba,
      `${Math.round(A)} m² × (${p.u_pred} − ${p.u_po}) W/(m²K) × ${D.model.kKh_ucinkoviti} kKh${D.model.faktor_prihranka_po_stanju_ovoja[v.stanje] < 1 ? ` × ${D.model.faktor_prihranka_po_stanju_ovoja[v.stanje]} (ovoj že ${v.stanje === 'delno' ? 'delno' : ''} izoliran)` : ''} = ${Math.round(dq)} kWh toplote; ÷ izkoristek ${eta} × ${pEn.toFixed(3)} €/kWh`);
  }
  if (v.ukrepi.includes('prezracevanje')) {
    const p = D.ukrepi[`prezracevanje_${v.prezracevanje || 'lokalno'}`];
    const kwh = p.prihranek_kwh, eur = kwh * pEn;
    row('prezracevanje', p.ime, strosekUkrepa(D, 'prezracevanje', v, n), kwh, eur, p.zivljenjska_doba, `${kwh} kWh na leto (Eko sklad) × ${pEn.toFixed(3)} €/kWh`);
  }
  // toplotna črpalka: najprej sama (na sedanjem ovoju), nato pri paketu z manjšo potrebo po toploti
  const st1 = stanjePo(v.stanje, v.ukrepi);
  // po ovoju: fizikalni prihranek, a ne manj od tabele Qh,nd za doseženo stanje ovoja (prezračevalne izgube, topla voda)
  const Q1 = ovoj.length ? Math.min(Q0, Math.max(Q0 - dQ, potrebnaToplota(D, v, st1))) : Q0;
  if (v.ukrepi.includes('tc')) {
    const p = D.ukrepi[`tc_${v.tc_vrsta || 'zrak_voda'}`];
    const Q = Q1, st = ovoj.length ? st1 : v.stanje;
    const moc = mocTC(D, Q), moc0 = mocTC(D, Q0);
    const staro = (Q / eta) * pEn, novo = (Q / scop(D, st, v)) * pEl, eur = staro - novo;
    const c = strosekUkrepa(D, 'tc', v, n, moc), c0 = strosekUkrepa(D, 'tc', v, n, moc0);
    row('tc', p.ime, c, Q / eta - Q / scop(D, st, v), eur, p.zivljenjska_doba,
      `toplota ${Math.round(Q)} kWh: danes ${Math.round(Q)} ÷ ${eta} × ${pEn.toFixed(3)} € = ${Math.round(staro)} €, s črpalko ${Math.round(Q)} ÷ SCOP ${scop(D, st, v).toFixed(1)} × ${pEl.toFixed(3)} € = ${Math.round(novo)} €; moč ${moc} kW`,
      { moc_kw: moc, moc_brez_ovoja_kw: moc0, strosek_brez_ovoja: c0 });
  }
  // paket: ena vsota namesto seštevka (ovoj zmanjša prihranek črpalke in obratno)
  const stPkt = st1;
  const staro = (Q0 / eta) * pEn;
  const vent = v.ukrepi.includes('prezracevanje') ? D.ukrepi[`prezracevanje_${v.prezracevanje || 'lokalno'}`].prihranek_kwh : 0;
  const novo = v.ukrepi.includes('tc') ? (Math.max(0, Q1 - vent * eta) / scop(D, stPkt, v)) * pEl : (Math.max(0, Q1 - vent * eta) / eta) * pEn;
  const paket = {
    strosek: out.reduce((s, r) => s + r.strosek, 0),
    spodbuda: out.reduce((s, r) => s + r.spodbuda_izbrana, 0),
    spodbuda_nps: out.reduce((s, r) => s + r.spodbuda_nps, 0),
    prihranek_eur: staro - novo,
    stroski_danes: staro,
  };
  return { Q0: Math.round(Q0), Q1: Math.round(Q1), stanje_po: st1, rezultati: out, paket: { ...paket,
    doba: [povracilo(paket.strosek, 0, paket.prihranek_eur), povracilo(paket.strosek, paket.spodbuda, paket.prihranek_eur), povracilo(paket.strosek, paket.spodbuda_nps, paket.prihranek_eur)] as [number | null, number | null, number | null] },
    bonus: bonusNPS(D, v), celovita: celovita(v) };
}

export const zaokrozi = r1;

/** Zgodba »Dve hiši, ista ulica«: kumulativni stroški (naložbe po odbitku spodbude po pozivu 2026 + energija) po letih za vsak
 *  vrstni red ukrepov in za hišo brez prenove. Tržne cene: fasada strosek_trzni_eur_m2, črpalka tc_trzni_eur_kw × moč ob vgradnji. */
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
          c = moc * S.tc_trzni_eur_kw; sp = spodbuda(D, 'tc', c, v0);
        } else {
          c = v0.povrsina * D.ukrepi[k.ukrep].povrsina_na_m2_tlorisa * D.ukrepi[k.ukrep].strosek_trzni_eur_m2; sp = spodbuda(D, k.ukrep, c, v0);
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
