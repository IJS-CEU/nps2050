// Infografični posnetek »NPS 2050 v eni minuti« (64 s, brez govora, s podnapisi): node tests/video.mjs
// Številke iz public/data/*.json; vsaka sličica se izriše deterministično (render(t)) in posname, ffmpeg sestavi MP4
// z nevtralno podlago, ustvarjeno iz čistih tonov (brez avtorskih pravic). Izhod v public/mediji/:
//   nps2050-v-eni-minuti.mp4 (1920×1080), nps2050-v-eni-minuti-kvadrat.mp4 (1080×1080), .vtt (podnapisi), -poster.jpg.
// Zaženi po vsaki osvežitvi podatkov (traja nekaj minut). FFMPEG: pot do ffmpeg.exe (privzeto namestitev winget).
import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = process.cwd();
const J = (n) => JSON.parse(readFileSync(resolve(root, 'public/data', `${n}.json`), 'utf-8'));
const FFMPEG = process.env.FFMPEG || (() => {
  const base = resolve(process.env.LOCALAPPDATA || '', 'Microsoft/WinGet/Packages');
  const pkg = existsSync(base) && readdirSync(base).find((d) => d.startsWith('Gyan.FFmpeg'));
  if (!pkg) return 'ffmpeg';
  const sub = readdirSync(resolve(base, pkg)).find((d) => d.startsWith('ffmpeg-'));
  return resolve(base, pkg, sub, 'bin', 'ffmpeg.exe');
})();
const FPS = 25, DUR = 64;
const nf = (v, d = 0) => v.toLocaleString('sl-SI', { minimumFractionDigits: d, maximumFractionDigits: d, useGrouping: 'always' });

// ---------------------------------------------------------------- podatki
const sf = J('stavbni_fond'), ix = J('obcine_index'), tr = J('trajektorija'), kz = J('kazalniki'), pk = J('paketi_prenove'), dr = J('drsnik'), meta = J('meta');
const em = kz.items.find((i) => i.id === 'emisije');
const emis50 = em.values.at(-1).value;
const emis23 = em.baseline.value;
const traj = tr.kwh_m2; const wpb = tr.zgodba.wpb;
const hisa = sf.categories.find((c) => c.id === 'HISA'), blok = sf.categories.find((c) => c.id === 'BLOKI');
const T = pk.tipi.find((t) => t.id === 'hisa_do1980'), V = T.variante.find((v) => v.id === 'olje'), C = V.paketi.find((p) => p.id === 'celovita');
const S0 = dr.referenca, M30 = dr.polozaji.find((p) => p.epbd_2030);
// Prizor 2: kje smo na poti do mejnika EPBD 2030 (drsnik: ocena stanja 2025 iz registrov in bilance, sedanja praksa S0)
const G = { b: dr.nps[0], n: dr.ocena_2025.osrednja, lo: dr.ocena_2025.spodnja, hi: dr.ocena_2025.zgornja,
  c: dr.epbd_max.find((e) => e.year === 2030).max, s0: S0.kwh_m2[dr.years.indexOf(2030)] };
G.pot = Math.round(100 * (G.b - G.n) / (G.b - G.c));
const zm = (v) => Math.round(100 * (1 - v / G.b)); G.zm = zm;
G.dosl = Math.round(100 * (1 - G.n / G.b)); G.cilj = Math.round(100 * (1 - G.c / G.b)); G.se = Math.round(100 * (1 - G.c / G.n));
G.ime = G.pot >= 30 && G.pot <= 37 ? ['tretjina', 'tretjino', 'dve tretjini'] : [`${G.pot} %`, `${G.pot} %`, `${100 - G.pot} %`];
// Prizor 5: stopnja prenove 2026–2030 → raba energije leta 2030 (drsnik, ocena stanja 2025)
const i30 = dr.years.indexOf(2030);
const RR = [{ ...S0, tag: 'danes' }, ...dr.polozaji.map((p) => ({ ...p, tag: p.id === dr.privzeto ? 'NPS' : '' }))]
  .map((p) => ({ tot: p.stopnja_2026_2030_pct, deep: p.celovito_2026_2030_pct, v: p.kwh_m2[i30], ok: p.kwh_m2[i30] <= G.c, tag: p.tag }))
  .sort((x, y) => x.tot - y.tot);
const D = {
  stavb: sf.segments.skupaj.buildings, povrsina: sf.segments.skupaj.area_mio_m2, pre81: ix.si.pre1981_res_area_pct,
  G, RR, pe20: traj.nps[0], pe50: traj.nps.at(-1), red: Math.round(100 * (1 - traj.nps.at(-1) / traj.nps[0])), emRed: Math.round(100 * (1 - emis50 / emis23)),
  thrH: hisa.worst_43.threshold, thrB: blok.worst_43.threshold, wpbA: wpb.area_mio_m2, wpbPE: wpb.avg_pe_2020, wpbY: wpb.years, wpbP: wpb.renovated_pct,
  pov: T.povrsina, ogr: V.ogrevanje, rp: V.razred_pred, pep: V.pe_pred, rpo: C.razred_po, pepo: C.pe_po,
  s25: Math.round(C.strosek_p25 / 1000), s75: Math.round(C.strosek_p75 / 1000), sp0: Math.round(C.spodbuda_eko_eur / 1000), sp1: Math.round(C.spodbuda_dod_eur / 1000),
  prih: Math.round(C.prihranek_eur / 10) * 10, pred: Math.round(V.paketi[0].stroski_pred_leto / 10) * 10,
  s0: S0.stopnja_2026_2030_pct, s0c: S0.celovito_2026_2030_pct, m: M30.stopnja_2026_2030_pct, mc: M30.celovito_2026_2030_pct,
  krat: Math.round(M30.celovito_2026_2030_pct / S0.celovito_2026_2030_pct),
};
const [dy, dm] = meta.draft_date.split('-');
const MES = ['januar', 'februar', 'marec', 'april', 'maj', 'junij', 'julij', 'avgust', 'september', 'oktober', 'november', 'december'];
const datum = `${MES[Number(dm) - 1]} ${dy}`;

// Podnapisi: [začetek, konec, besedilo]
const CAPS = [
  [0.6, 5.2, `Slovenija ima ${nf(Math.round(D.stavb / 1000))} tisoč stavb s ${nf(D.povrsina, 1)} mio m² uporabne površine.`],
  [5.4, 9.8, `Več kot polovica stanovanjske površine je nastala pred prvimi toplotnimi predpisi leta 1981.`],
  [10.4, 15.2, `Do leta 2030 mora raba energije stanovanjskih stavb na m² pasti za ${G.cilj} %. V petih letih smo prehodili šele ${G.ime[1]} poti.`],
  [15.4, 19.8, `S sedanjim tempom prenove bomo cilj zgrešili. Za ${G.ime[2]} poti nam ostane pet let.`],
  [20.4, 25.2, `Prednost imajo energetsko najslabše stavbe – 43 % stanovanjskih stavb z najvišjo rabo energije.`],
  [25.4, 29.8, `Do leta 2030 naj bo prenovljenih ${D.wpbP[0]} % teh stavb, do leta 2050 vse.`],
  [30.4, 35.6, `Tipična hiša, zgrajena pred letom 1980, je danes v razredu ${D.rp}.`],
  [35.8, 41.8, `Celovita prenova ovoja in sistemov jo pripelje v razred ${D.rpo} in prihrani več kot tisoč evrov na leto. Stroški so priznani stroški Eko sklada, dejanski so višji.`],
  [42.4, 47.6, `Danes prenovimo ${nf(D.s0, 1)} % stanovanjske površine na leto, a le ${nf(D.s0c, 1)} % celovito – zato pristanemo daleč od cilja.`],
  [47.8, 53.8, `Cilj za 2030 dosežemo šele s približno ${nf(D.m, 0)} % prenov na leto, od tega ${nf(D.mc, 1)} % celovitih – ${D.krat}-krat več celovitih kot danes.`],
  [54.4, 63.6, `Preverite svojo stavbo, poglejte svojo občino in raziščite, kaj bi prinesla hitrejša prenova.`],
];
const SCENES = [[0, 10], [10, 20], [20, 30], [30, 42], [42, 54], [54, 64]];

// ---------------------------------------------------------------- HTML
const data = (p, type) => `data:${type};base64,${readFileSync(resolve(root, p)).toString('base64')}`;
const font = (p) => data(`node_modules/@fontsource-variable/${p}`, 'font/woff2');
const CLS = ['A', 'B', 'C', 'D', 'E', 'F', 'G'];
const COL = { A: '#0B7A45', B: '#62B044', C: '#D9C92B', D: '#F0AE2E', E: '#EC842B', F: '#DE5A2B', G: '#C4302C' };

function html(sq) {
  const W = sq ? 1080 : 1920, H = 1080;
  const P = sq ? 70 : 120;                // rob
  const inner = W - 2 * P;
  // trajektorija (SVG)
  const gx = (v) => (100 * (G.b - v) / (G.b - G.c)).toFixed(2) + '%';
  const dots = Array.from({ length: sq ? 100 : 200 }, (_, i) => `<i data-i="${i}"></i>`).join('');
  return `<!doctype html><html lang="sl"><head><meta charset="utf-8"><style>
@font-face { font-family: M; src: url(${font('manrope/files/manrope-latin-ext-wght-normal.woff2')}); font-weight: 200 800; }
@font-face { font-family: M; src: url(${font('manrope/files/manrope-latin-wght-normal.woff2')}); font-weight: 200 800; unicode-range: U+0000-00FF; }
@font-face { font-family: S; src: url(${font('source-serif-4/files/source-serif-4-latin-ext-wght-normal.woff2')}); font-weight: 200 900; }
@font-face { font-family: S; src: url(${font('source-serif-4/files/source-serif-4-latin-wght-normal.woff2')}); font-weight: 200 900; unicode-range: U+0000-00FF; }
* { margin: 0; box-sizing: border-box; }
body { width: ${W}px; height: ${H}px; background: #333D22; color: #F5F2E8; font-family: M; overflow: hidden; position: relative; }
.sc { position: absolute; inset: 0; opacity: 0; }
.k { position: absolute; left: ${P}px; top: ${sq ? 70 : 90}px; font-size: ${sq ? 22 : 26}px; font-weight: 800; letter-spacing: .14em; text-transform: uppercase; color: #D6B25E; }
h1 { position: absolute; left: ${P}px; right: ${P}px; top: ${sq ? 112 : 138}px; font-family: S; font-weight: 700; font-size: ${sq ? 60 : 80}px; line-height: 1.05; }
.sub { position: absolute; left: ${P}px; right: ${P}px; top: ${sq ? 250 : 250}px; font-size: ${sq ? 28 : 34}px; color: #DAD8C9; }
.sig { position: absolute; right: ${P}px; top: ${sq ? 30 : 92}px; font-size: ${sq ? 18 : 22}px; color: #DAD8C9; font-weight: 700; letter-spacing: .06em; }
.cap { position: absolute; left: 0; right: 0; bottom: 0; height: ${sq ? 150 : 120}px; background: rgba(0,0,0,.45); display: grid; place-items: center; font-size: ${sq ? 28 : 32}px; padding: 0 ${sq ? 60 : 140}px; text-align: center; line-height: 1.3; }
.prog { position: absolute; left: ${P}px; right: ${P}px; bottom: ${sq ? 160 : 132}px; display: flex; gap: 8px; }
.prog b { flex: 1; height: 4px; border-radius: 2px; background: rgba(245,242,232,.18); position: relative; overflow: hidden; }
.prog b i { position: absolute; inset: 0; background: #D6B25E; transform-origin: left; transform: scaleX(0); }
.big { font-family: S; font-weight: 700; color: #F5F2E8; }
.gold { color: #D6B25E; }
/* 1 */
#s1 .num { position: absolute; left: ${P}px; top: ${sq ? 270 : 330}px; font-size: ${sq ? 120 : 150}px; }
#s1 .num small { font-family: M; font-size: ${sq ? 34 : 40}px; color: #D6B25E; font-weight: 700; margin-left: 16px; }
#s1 .dots { position: absolute; left: ${P}px; top: ${sq ? 480 : 540}px; width: ${inner}px; display: grid; grid-template-columns: repeat(${sq ? 20 : 40}, 1fr); gap: ${sq ? 8 : 10}px; }
#s1 .dots i { display: block; aspect-ratio: 1; border-radius: 50%; background: #F5F2E8; opacity: 0; }
#s1 .leg { position: absolute; left: ${P}px; top: ${sq ? 790 : 830}px; font-size: ${sq ? 26 : 30}px; color: #DAD8C9; }
#s1 .leg i { display: inline-block; width: 22px; height: 22px; border-radius: 50%; background: #EC842B; vertical-align: -3px; margin-right: 10px; }
/* 2 */
.chip { background: rgba(245,242,232,.08); border: 2px solid rgba(214,178,94,.55); border-radius: 22px; padding: 22px 30px; opacity: 0; }
.chip b { display: block; font-family: S; font-size: ${sq ? 56 : 72}px; line-height: 1; }
.chip span { font-size: ${sq ? 22 : 26}px; color: #DAD8C9; }
#s2 .trk { position: absolute; left: ${P}px; right: ${P}px; top: ${sq ? 440 : 450}px; height: 44px; border-radius: 22px; background: rgba(245,242,232,.15); }
#s2 .trk > i { position: absolute; top: 0; bottom: 0; left: 0; border-radius: 22px; }
#s2 .f { background: #8FD19E; width: 0; }
#s2 .z { border: 3px dashed rgba(245,242,232,.7); background: none !important; opacity: 0; }
#s2 .r { background: repeating-linear-gradient(135deg, #DE5A2B 0 12px, #C4302C 12px 24px); opacity: 0; border-radius: 0 22px 22px 0 !important; }
#s2 .lb { position: absolute; white-space: nowrap; font-size: ${sq ? 24 : 28}px; color: #DAD8C9; opacity: 0; }
#s2 .lb b { font-family: S; font-size: ${sq ? 38 : 46}px; color: #F5F2E8; margin-left: 8px; }
#s2 .up { bottom: 62px; } #s2 .dn { top: 62px; }
#s2 .lb.gold, #s2 .lb.gold b { color: #D6B25E; }
#s2 .lb.red b { color: #EC842B; }
#s2 .cs { position: absolute; left: ${P}px; right: ${P}px; top: ${sq ? 640 : 680}px; display: grid; grid-template-columns: 1fr 1fr; gap: ${sq ? 20 : 36}px; }
#s2 .chip b { font-size: ${sq ? 52 : 64}px; }
#s2 .chip.red b { color: #EC842B; }
#s2 .nt { position: absolute; left: ${P}px; right: ${P}px; top: ${sq ? 850 : 860}px; font-size: ${sq ? 19 : 22}px; color: #B9B7A8; opacity: 0; }
/* 3 */
#s3 .grid { position: absolute; left: ${P}px; top: ${sq ? 270 : 330}px; width: ${sq ? inner : 900}px; display: grid; grid-template-columns: repeat(20, 1fr); gap: 8px; }
#s3 .grid i { display: block; aspect-ratio: 1; border-radius: 4px; background: rgba(245,242,232,.25); }
#s3 .grid i.w { background: rgba(245,242,232,.25); }
#s3 .info { position: absolute; ${sq ? `left: ${P}px; right: ${P}px; top: 530px;` : `left: ${P + 960}px; top: 330px; width: ${inner - 960}px;`} font-size: ${sq ? 26 : 30}px; color: #DAD8C9; line-height: 1.4; }
#s3 .info b { color: #F5F2E8; }
#s3 .bars { position: absolute; ${sq ? `left: ${P}px; top: 640px; width: ${inner}px;` : `left: ${P + 960}px; top: 560px; width: ${inner - 960}px;`} }
#s3 .bar { display: grid; grid-template-columns: 90px 1fr 100px; align-items: center; gap: 14px; margin: ${sq ? 6 : 12}px 0; font-size: 26px; }
#s3 .bar s { display: block; height: 22px; background: rgba(245,242,232,.15); border-radius: 11px; overflow: hidden; text-decoration: none; }
#s3 .bar s i { display: block; height: 100%; background: #DE5A2B; width: 0; }
/* 4 */
#s4 .scale { position: absolute; left: ${P + (sq ? 0 : 140)}px; top: 400px; width: ${sq ? inner : 1400}px; height: 90px; display: grid; grid-template-columns: repeat(7, 1fr); gap: 6px; }
#s4 .scale span { display: grid; place-items: center; font-weight: 800; font-size: 40px; color: #fff; border-radius: 8px; text-shadow: 0 1px 2px rgba(0,0,0,.35); }
#s4 .mk { position: absolute; top: 342px; width: 0; }
#s4 .mk b { position: absolute; left: 0; transform: translateX(-50%); white-space: nowrap; font-size: ${sq ? 24 : 28}px; font-weight: 800; }
#s4 .mk i { position: absolute; left: -3px; top: 42px; width: 6px; height: 18px; background: #F5F2E8; border-radius: 3px; }
#s4 .m1 b { color: #8FD19E; } ${sq ? '#s4 .mk b { transform: translateX(-30px); }' : ''} #s4 .m1 i { background: #8FD19E; }
#s4 .lab { position: absolute; left: ${P}px; right: ${P}px; top: 515px; text-align: center; font-size: ${sq ? 24 : 30}px; color: #DAD8C9; }
#s4 .cards { position: absolute; left: ${P}px; right: ${P}px; top: ${sq ? 580 : 610}px; display: grid; grid-template-columns: ${sq ? '1fr' : 'repeat(3, 1fr)'}; gap: ${sq ? 14 : 36}px; }
.card { background: rgba(245,242,232,.08); border: 2px solid rgba(214,178,94,.55); border-radius: 22px; padding: ${sq ? '14px 26px' : '34px 38px'}; opacity: 0; ${sq ? 'display: flex; align-items: baseline; gap: 20px;' : ''} }
.card .v { font-family: S; font-weight: 700; font-size: ${sq ? 40 : 64}px; line-height: 1.05; white-space: nowrap; }
.card .v small { font-family: M; font-size: ${sq ? 22 : 30}px; font-weight: 700; color: #D6B25E; }
.card .l { font-size: ${sq ? 20 : 26}px; color: #DAD8C9; margin-top: ${sq ? 0 : 12}px; line-height: 1.3; }
/* 5 */
#s5 .hd { position: absolute; top: ${sq ? 268 : 290}px; font-size: ${sq ? 19 : 24}px; color: #DAD8C9; line-height: 1.3; }
#s5 .hd i { display: inline-block; width: 18px; height: 18px; border-radius: 4px; vertical-align: -2px; margin: 0 6px 0 14px; }
#s5 .h1 { left: ${P}px; width: ${sq ? 420 : 870}px; } #s5 .h2 { left: ${P + (sq ? 450 : 880)}px; right: ${P}px; }
#s5 .rows { position: absolute; left: ${P}px; right: ${P}px; top: ${sq ? 360 : 370}px; }
#s5 .row { position: relative; height: ${sq ? 92 : 94}px; opacity: 0; }
#s5 .rt { position: absolute; left: 0; top: 4px; font-family: S; font-weight: 700; font-size: ${sq ? 36 : 44}px; }
#s5 .rs { position: absolute; left: 330px; top: 58px; font-size: 20px; color: #B9B7A8; }
#s5 .rt small { font-family: M; font-size: ${sq ? 18 : 22}px; font-weight: 600; color: #DAD8C9; margin-left: 8px; }
#s5 .tg { display: inline-block; font-family: M; font-size: ${sq ? 15 : 18}px; font-weight: 800; letter-spacing: .06em; text-transform: uppercase; padding: 3px 10px; border-radius: 99px; margin-left: 10px; vertical-align: 6px; background: #D6B25E; color: #333D22; }
#s5 .rb { position: absolute; left: ${sq ? 0 : 330}px; top: ${sq ? 54 : 18}px; height: ${sq ? 20 : 30}px; display: flex; border-radius: 6px; overflow: hidden; }
#s5 .rb .d { background: #8FD19E; } #s5 .rb .p { background: rgba(245,242,232,.35); }
#s5 .sc2 { position: absolute; left: ${sq ? 450 : 880}px; right: 0; top: 0; bottom: 0; }
#s5 .ln { position: absolute; top: ${sq ? 44 : 38}px; height: 4px; background: rgba(245,242,232,.25); left: 0; }
#s5 .dt { position: absolute; top: ${sq ? 32 : 26}px; z-index: 1; width: 28px; height: 28px; margin-left: -14px; border-radius: 50%; }
#s5 .dv { position: absolute; top: ${sq ? -10 : -22}px; font-family: S; font-weight: 700; font-size: ${sq ? 28 : 34}px; white-space: nowrap; }
#s5 .tl { position: absolute; top: ${sq ? 340 : 360}px; height: ${sq ? 470 : 480}px; width: 4px; margin-left: -2px; background: #D6B25E; opacity: 0; }
#s5 .tl b { position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%); white-space: nowrap; color: #D6B25E; font-size: ${sq ? 20 : 24}px; padding-bottom: 4px; }
#s5 .ok { position: absolute; top: ${sq ? 340 : 360}px; height: ${sq ? 470 : 480}px; right: ${P}px; background: rgba(143,209,158,.10); opacity: 0; }
/* 6 */
#s6 .btns { position: absolute; left: ${P}px; right: ${P}px; top: ${sq ? 330 : 340}px; display: grid; gap: 22px; justify-items: start; }
#s6 .btn { font-size: ${sq ? 40 : 48}px; font-weight: 800; padding: 18px 40px; border-radius: 999px; background: #D6B25E; color: #333D22; opacity: 0; }
#s6 .url { position: absolute; left: ${P}px; top: ${sq ? 720 : 720}px; font-family: S; font-size: ${sq ? 46 : 64}px; font-weight: 700; opacity: 0; }
#s6 .mus { position: absolute; left: ${P}px; right: ${P}px; top: ${sq ? 862 : 872}px; font-size: ${sq ? 17 : 19}px; color: #A9A797; opacity: 0; }
#s6 .note { position: absolute; left: ${P}px; right: ${P}px; top: ${sq ? 800 : 820}px; font-size: ${sq ? 20 : 24}px; color: #DAD8C9; opacity: 0; }
</style></head><body>
<p class="sig">IJS CEU · strokovne podlage NPS 2050 · osnutek, ${datum}</p>

<section class="sc" id="s1"><p class="k">Izhodišče</p><h1>Stavbe v Sloveniji</h1>
  <p class="num big"><span id="cnt">0</span><small>stavb · ${nf(D.povrsina, 1)} mio m²</small></p>
  <div class="dots">${dots}</div>
  <p class="leg"><i></i>zgrajeno pred letom 1981: ${nf(D.pre81, 0)} % stanovanjske površine</p></section>

<section class="sc" id="s2"><p class="k">Cilj 2030</p><h1>${G.pot >= 30 && G.pot <= 37 ? 'Prehodili smo šele tretjino poti' : `Prehodili smo šele ${G.pot} % poti`}</h1>
  <div class="trk">
    <i class="f" id="gf"></i>
    <i class="z" id="gz" style="left:${gx(G.n)};width:calc(${gx(G.s0)} - ${gx(G.n)})"></i>
    <i class="r" id="gr" style="left:${gx(G.s0)};right:0"></i>
    <span class="lb dn" id="l0" style="left:0">izhodišče<b>2020</b></span>
    <span class="lb up" id="l1" style="left:${gx(G.n)};transform:translateX(-50%)">danes<b>−${zm(G.n)} %</b></span>
    <span class="lb up gold" id="l2" style="right:0">cilj 2030<b>−${zm(G.c)} %</b></span>
    <span class="lb dn red" id="l3" style="left:${gx(G.s0)};transform:translateX(-${sq ? 50 : 30}%)">s sedanjim tempom 2030<b>−${zm(G.s0)} %</b></span>
  </div>
  <div class="cs"><div class="chip" id="ch1"><b>−${G.dosl} %</b><span>doseženo 2020–2025</span></div><div class="chip red" id="ch2"><b>−${G.se} %</b><span>potrebno 2025–2030</span></div></div>
  <p class="nt" id="gn">Raba energije stanovanjskih stavb na kvadratni meter v primerjavi z letom 2020, kot jo meri evropska direktiva o stavbah (EPBD). Danes: ocena IJS CEU za leto 2025 (razpon −${zm(G.hi)} do −${zm(G.lo)} %).</p></section>

<section class="sc" id="s3"><p class="k">Najslabše najprej</p><h1>43 % stavb z najvišjo rabo</h1>
  <div class="grid">${Array.from({ length: 100 }, (_, i) => `<i data-i="${i}"></i>`).join('')}</div>
  <p class="info">Hiše nad <b>${D.thrH}</b>, bloki nad <b>${D.thrB} kWh/(m²·a)</b> primarne energije: <b>${nf(D.wpbA, 1)} mio m²</b>, povprečno <b>${D.wpbPE} kWh/(m²·a)</b>.</p>
  <div class="bars">${D.wpbY.map((y, i) => `<div class="bar"><span>${y}</span><s><i data-p="${D.wpbP[i]}"></i></s><b>${D.wpbP[i]} %</b></div>`).join('')}</div></section>

<section class="sc" id="s4"><p class="k">Kaj to pomeni za vašo hišo</p><h1>Celovita prenova stare hiše</h1>
  <p class="sub">Hiša, zgrajena do leta 1980 · ${D.pov} m² · ogrevanje na ${D.ogr}</p>
  <div class="scale">${CLS.map((x) => `<span style="background:${COL[x]}">${x}</span>`).join('')}</div>
  <div class="mk m0"><b>danes: ${D.pep} kWh/(m²·a)</b><i></i></div>
  <div class="mk m1"><b>po prenovi: ${D.pepo} kWh/(m²·a)</b><i></i></div>
  <p class="lab">izolacija fasade in strehe · nova okna · toplotna črpalka · prezračevanje</p>
  <div class="cards">
    <div class="card"><div class="v">${D.s25}–${D.s75} <small>tisoč €</small></div><div class="l">priznani stroški (Eko sklad);${sq ? ' ' : '<br>'}dejanski so višji</div></div>
    <div class="card"><div class="v">${D.sp0} → ${D.sp1} <small>tisoč €</small></div><div class="l">spodbuda danes → po predlogu NPS</div></div>
    <div class="card"><div class="v">${nf(D.prih)} <small>€ na leto</small></div><div class="l">manj za energijo${sq ? ' ' : '<br>'}(danes okoli ${nf(D.pred)} €)</div></div>
  </div></section>

<section class="sc" id="s5"><p class="k">Hitreje in globlje</p><h1>Celovitih prenov ${D.krat}-krat več</h1>
  <p class="hd h1">prenovljena površina na leto, 2026–2030${sq ? '<br>' : ':'}<i style="background:#8FD19E;margin-left:${sq ? 0 : 14}px"></i>celovito<i style="background:rgba(245,242,232,.35)"></i>posamezni ukrepi</p>
  <p class="hd h2">manj energije na m² leta 2030${sq ? '<br>' : ' '}(glede na 2020)</p>
  <div class="ok" id="s5ok"></div><div class="tl" id="s5tl"><b>cilj −${zm(G.c)} %</b></div>
  <div class="rows">${D.RR.map((r, i) => `<div class="row" id="r${i}">
    ${sq ? '' : `<span class="rs">od tega ${nf(r.deep, 1)} % celovito</span>`}<span class="rt">${nf(r.tot, 1)} %${r.tag ? `<span class="tg">${r.tag}</span>` : ''}</span>
    <span class="rb"><i class="d"></i><i class="p"></i></span>
    <span class="sc2"><i class="ln"></i><i class="dt" style="background:${r.ok ? '#8FD19E' : '#EC842B'}"></i><b class="dv" style="color:${r.ok ? '#8FD19E' : '#EC842B'};transform:translateX(${r.ok ? -25 : -80}%)">−${zm(r.v)} %</b></span></div>`).join('')}</div></section>

<section class="sc" id="s6"><p class="k">Kje najdete več</p><h1>Strokovne podlage NPS 2050</h1>
  <div class="btns"><span class="btn">Preverite svojo stavbo</span><span class="btn">Moja občina</span><span class="btn">Kaj pa, če?</span></div>
  <p class="url">ijs-ceu.github.io/nps2050</p>
  <p class="note">Številke iz osnutka NPS 2050 (${datum}) in strokovnih podlag IJS CEU; do sprejema načrta se lahko spremenijo.</p>
  ${process.env.MUSIC_CREDIT ? `<p class="mus">Glasba: ${process.env.MUSIC_CREDIT}</p>` : ''}</section>

<div class="prog">${SCENES.map(() => '<b><i></i></b>').join('')}</div>
<div class="cap"><span id="cap"></span></div>
<script>
const SC = ${JSON.stringify(SCENES)}, CAPS = ${JSON.stringify(CAPS)}, D = ${JSON.stringify(D)}, SQ = ${sq};
const cl = (x) => Math.max(0, Math.min(1, x)), ease = (x) => { x = cl(x); return x < .5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2; };
const $ = (s) => document.querySelector(s), $$ = (s) => [...document.querySelectorAll(s)];
const fadeUp = (el, t, t0, d = .6) => { const p = ease((t - t0) / d); el.style.opacity = p; el.style.transform = 'translateY(' + (1 - p) * 24 + 'px)'; };
const scW = SQ ? ${inner} : 1400, scL = ${P} + (SQ ? 0 : 140);
window.render = (t) => {
  SC.forEach(([a, b], i) => { const el = $('#s' + (i + 1)); const o = Math.min(cl((t - a) / .5), i === SC.length - 1 ? 1 : cl((b - t) / .5)); el.style.opacity = o; el.style.visibility = o > 0 ? 'visible' : 'hidden';
    $$('.prog i')[i].style.transform = 'scaleX(' + cl((t - a) / (b - a)) + ')'; });
  const c = CAPS.find(([a, b]) => t >= a && t <= b); const cap = $('#cap'); cap.textContent = c ? c[2] : '';
  cap.style.opacity = c ? Math.min(cl((t - c[0]) / .3), cl((c[1] - t) / .3)) : 0;
  // 1
  { const a = 0; $('#cnt').textContent = Math.round(D.stavb * ease((t - a - .8) / 2.5)).toLocaleString('sl-SI');
    const dd = $$('#s1 .dots i'), n = dd.length; dd.forEach((d, i) => { d.style.opacity = cl((t - a - 1 - i * 2.4 / n) / .3); const old = i < Math.round(n * D.pre81 / 100);
      d.style.background = old && t > a + 5.6 + i * 2 / n ? '#EC842B' : '#F5F2E8'; });
    fadeUp($('#s1 .leg'), t, a + 6); }
  // 2
  { const a = 10; $('#l0').style.opacity = cl((t - a - .6) / .4); $('#l2').style.opacity = cl((t - a - 1) / .4);
    $('#gf').style.width = 'calc(' + D.G.pot * ease((t - a - 1.5) / 2) + '% + ' + (1 - ease((t - a - 1.5) / 2)) * 0 + 'px)'; $('#l1').style.opacity = cl((t - a - 3.3) / .4);
    fadeUp($('#ch1'), t, a + 3.6); $('#gz').style.opacity = cl((t - a - 5.4) / .5); $('#l3').style.opacity = cl((t - a - 5.6) / .5);
    $('#gr').style.opacity = cl((t - a - 6.4) / .5); fadeUp($('#ch2'), t, a + 6.8); $('#gn').style.opacity = cl((t - a - 7.4) / .5); }
  // 3
  { const a = 20; $$('#s3 .grid i').forEach((d, i) => { const w = i >= 57; d.style.background = w && t > a + 1.5 + (i - 57) * .03 ? '#DE5A2B' : 'rgba(245,242,232,.25)'; });
    fadeUp($('#s3 .info'), t, a + 2.5); $$('#s3 .bar i').forEach((b, i) => { b.style.width = (b.dataset.p * ease((t - a - 4.5 - i * .4) / .8)) + '%'; }); }
  // 4
  { const a = 30, x = (k) => scL + (k + .5) * scW / 7, i0 = 'ABCDEFG'.indexOf(D.rp), i1 = 'ABCDEFG'.indexOf(D.rpo);
    const m0 = $('#s4 .m0'), m1 = $('#s4 .m1'); m0.style.left = x(i0) + 'px'; m0.style.opacity = Math.min(cl((t - a - 1.5) / .5), t > a + 5 ? .35 : 1);
    m1.style.left = (x(i0) + (x(i1) - x(i0)) * ease((t - a - 4) / 1.6)) + 'px'; m1.style.opacity = cl((t - a - 3.6) / .3);
    fadeUp($('#s4 .lab'), t, a + 5.6); $$('#s4 .card').forEach((c, i) => fadeUp(c, t, a + 6.2 + i * .9)); }
  // 5
  { const a = 42, BW = SQ ? 400 : 520, x0 = ${P} + (SQ ? 450 : 880), SW = ${W} - ${P} - x0;
    const sx = (v) => (v > 255 ? 0 : (255 - v) / 55) * SW, tx = x0 + sx(D.G.c);
    $$('#s5 .hd').forEach((h) => fadeUp(h, t, a + .6));
    $('#s5tl').style.left = tx + 'px'; $('#s5tl').style.opacity = cl((t - a - 1) / .5);
    $('#s5ok').style.left = tx + 'px'; $('#s5ok').style.opacity = cl((t - a - 1) / .5);
    // vrstni red: najprej »danes«, nato ostale
    const ord = D.RR.map((r, i) => i).sort((i, j) => (D.RR[j].tag === 'danes') - (D.RR[i].tag === 'danes'));
    ord.forEach((i, k) => { const r = D.RR[i], t0 = a + 1.4 + (k === 0 ? 0 : 4.6 + (k - 1) * .5), row = $('#r' + i);
      row.style.opacity = cl((t - t0) / .4);
      const p = ease((t - t0 - .2) / 1), q = ease((t - t0 - .9) / 1.2);
      row.querySelector('.d').style.width = BW * r.deep / 4.2 * p + 'px'; row.querySelector('.p').style.width = BW * (r.tot - r.deep) / 4.2 * p + 'px';
      const x = sx(255 + (r.v - 255) * q); row.querySelector('.dt').style.left = x + 'px'; row.querySelector('.ln').style.width = x + 'px';
      const dv = row.querySelector('.dv'); dv.style.left = x + 'px'; dv.style.opacity = cl((t - t0 - 2) / .3); }); }
  // 6
  { const a = 54; $$('#s6 .btn').forEach((b, i) => fadeUp(b, t, a + .8 + i * .6)); fadeUp($('#s6 .url'), t, a + 3); fadeUp($('#s6 .note'), t, a + 3.8); const mu = $('#s6 .mus'); if (mu) mu.style.opacity = cl((t - a - 6) / .8); }
};
render(0);
</script></body></html>`;
}

// ---------------------------------------------------------------- izris in sestava
const out = resolve(root, 'public/mediji'); mkdirSync(out, { recursive: true });
const tmp = resolve(root, 'tests/_video_frames'); rmSync(tmp, { recursive: true, force: true }); mkdirSync(tmp, { recursive: true });
const vtt = 'WEBVTT\n\n' + CAPS.map(([a, b, s], i) => `${i + 1}\n${ts(a)} --> ${ts(b)}\n${s}\n`).join('\n');
function ts(s) { const h = Math.floor(s / 3600), m = Math.floor(s / 60) % 60, x = (s % 60).toFixed(3).padStart(6, '0'); return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${x}`; }
writeFileSync(resolve(out, 'nps2050-v-eni-minuti.vtt'), vtt, 'utf-8');

// nevtralna podlaga: počasi utripajoč akord iz čistih tonov (A–C#–E–A), z mehkim začetkom in koncem
const audio = resolve(tmp, 'podlaga.wav');
const expr = ['110', '164.81', '220', '277.18'].map((f, i) => `0.035*sin(2*PI*${f}*t)*(0.65+0.35*sin(2*PI*${(0.05 + i * 0.013).toFixed(3)}*t))`).join('+');
// MUSIC=pot/do/skladbe.mp3 [MUSIC_START=6] [MUSIC_CREDIT='Avtor – Naslov (vir)']: namesto tonov odsek skladbe (licenca mora dovoljevati objavo na spletu)
if (process.env.MUSIC) execFileSync(FFMPEG, ['-y', '-loglevel', 'error', '-ss', process.env.MUSIC_START || '6', '-t', String(DUR), '-i', process.env.MUSIC,
  '-af', `afade=t=in:d=1.5,afade=t=out:st=${DUR - 4.5}:d=4.5,loudnorm=I=-20:TP=-2:LRA=11`, '-ar', '48000', audio]);
else execFileSync(FFMPEG, ['-y', '-loglevel', 'error', '-f', 'lavfi', '-i', `aevalsrc=${expr}:s=48000:d=${DUR}`, '-af', `lowpass=f=1200,afade=t=in:d=3,afade=t=out:st=${DUR - 4}:d=4`, audio]);

const browser = await chromium.launch();
if (process.env.STILLS) {   // predogled: STILLS=3,14,25 node tests/video.mjs → tests/_video_tNN.png
  for (const sq of [false, true]) {
    const page = await browser.newPage({ viewport: { width: sq ? 1080 : 1920, height: 1080 } });
    await page.setContent(html(sq), { waitUntil: 'load' }); await page.evaluate(() => document.fonts.ready);
    for (const t of process.env.STILLS.split(',').map(Number)) { await page.evaluate((x) => window.render(x), t); await page.screenshot({ path: resolve(root, `tests/_video_${sq ? 'k' : 'w'}${t}.png`) }); }
  }
  await browser.close(); process.exit(0);
}
for (const [sq, name] of [[false, 'nps2050-v-eni-minuti'], [true, 'nps2050-v-eni-minuti-kvadrat']]) {
  const page = await browser.newPage({ viewport: { width: sq ? 1080 : 1920, height: 1080 } });
  await page.setContent(html(sq), { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready);
  const dir = resolve(tmp, name); mkdirSync(dir);
  for (let f = 0; f < FPS * DUR; f++) {
    await page.evaluate((t) => window.render(t), f / FPS);
    await page.screenshot({ path: resolve(dir, `f${String(f).padStart(5, '0')}.jpg`), type: 'jpeg', quality: 92 });
  }
  if (!sq) { await page.evaluate((t) => window.render(t), 38.5); await page.screenshot({ path: resolve(out, 'nps2050-v-eni-minuti-poster.jpg'), type: 'jpeg', quality: 85 }); }
  await page.close();
  execFileSync(FFMPEG, ['-y', '-loglevel', 'error', '-framerate', String(FPS), '-i', resolve(dir, 'f%05d.jpg'), '-i', audio,
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '23', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', process.env.MUSIC ? '160k' : '96k', '-shortest', '-movflags', '+faststart',
    resolve(out, `${name}.mp4`)]);
  console.log(`public/mediji/${name}.mp4`);
}
await browser.close();
rmSync(tmp, { recursive: true, force: true });
