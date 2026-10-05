// Infografični posnetek »Moja občina« (90 s, brez govora, s podnapisi): node tests/video_obcine.mjs
// Za medije in promocijo (ne za stran Moja občina). Zemljevidi: zbirni podatki iz public/data/obcine_index.json in obrisi iz
// zemljevid_obcine.geojson. Prizora 4 in 5: primera občin s številkami in grafi (OBC4, privzeto Ljubljana; OBC5, privzeto Ribnica).
// Izhod v public/mediji/: nps2050-moja-obcina.mp4 (1920×1080), …-kvadrat.mp4 (1080×1080), .vtt, -poster.jpg.
// Glasba kot pri tests/video.mjs: MUSIC=… MUSIC_CREDIT='…' [MUSIC_START=…]; predogled: STILLS=5,20 node tests/video_obcine.mjs
import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = process.cwd();
const J = (n) => JSON.parse(readFileSync(resolve(root, 'public/data', n), 'utf-8'));
const FFMPEG = process.env.FFMPEG || (() => {
  const base = resolve(process.env.LOCALAPPDATA || '', 'Microsoft/WinGet/Packages');
  const pkg = existsSync(base) && readdirSync(base).find((d) => d.startsWith('Gyan.FFmpeg'));
  if (!pkg) return 'ffmpeg';
  const sub = readdirSync(resolve(base, pkg)).find((d) => d.startsWith('ffmpeg-'));
  return resolve(base, pkg, sub, 'bin', 'ffmpeg.exe');
})();
const FPS = 25, DUR = 90, NAME = 'nps2050-moja-obcina';
const nf = (v, d = 0) => v.toLocaleString('sl-SI', { minimumFractionDigits: d, maximumFractionDigits: d, useGrouping: 'always' });

// ---------------------------------------------------------------- podatki
const ix = J('obcine_index.json'), geo = J('zemljevid_obcine.geojson'), meta = J('meta.json'), mo = J('obcine_model.json');
// Primera v prizorih 4 in 5 (OBC4, OBC5): Ljubljana in občina z dobrimi kazalniki (Ribnica: 76 % obnovljivih virov, nizke emisije)
const obc = (name) => { const i = ix.municipalities.find((m) => m.name === name), m = Object.values(mo.municipalities).find((x) => x.name === name);
  if (!i || !m) throw new Error('ni občine ' + name); return { ...i, ...m }; };
const SIM = mo.si;
const O4 = obc(process.env.OBC4 || 'Ljubljana'), O5 = obc(process.env.OBC5 || 'Ribnica');
const CAR = { el: ['elektrika', '#2A6FC9'], amb: ['toplota okolice', '#8FD19E'], gas: ['plin', '#9AA0A6'], elko: ['kurilno olje', '#5B4636'], bio: ['lesna biomasa', '#62B044'], dh: ['daljinska toplota', '#D6B25E'] };
const TOPC5 = Object.entries(O5.carriers_pct).sort((a, b) => b[1] - a[1])[0];
const tempo = (o) => o.t_dej_pct >= o.t_zah_pct ? 'več, kot zahteva NPS 2050' : `blizu potrebnih ${nf(o.t_zah_pct, 1)} %`;
const M = ix.municipalities, SI = ix.si;
const byEid = Object.fromEntries(M.map((m) => [m.eid, m]));
const rng = (k) => { const v = M.map((m) => m[k]).filter((x) => x != null); return [Math.min(...v), Math.max(...v)]; };
const sem = { 'na poti': 0, 'pod ciljem': 0, 'ni podatka': 0 }; M.forEach((m) => { sem[m.t_semafor] = (sem[m.t_semafor] || 0) + 1; });
const D = {
  n: M.length, pre: rng('pre1981_res_area_pct').map(Math.round), preSI: Math.round(SI.pre1981_res_area_pct),
  ove: rng('k_ove_pct').map(Math.round), oveSI: Math.round(SI.k_ove_pct), dh: Math.round(SI.k_dh_pot_pct), dhMax: Math.round(rng('k_dh_pot_pct')[1]),
  dej: SI.t_dej_pct, zah: SI.t_zah_pct, sem,
};
const [dy, dm] = meta.draft_date.split('-');
const MES = ['januar', 'februar', 'marec', 'april', 'maj', 'junij', 'julij', 'avgust', 'september', 'oktober', 'november', 'december'];
const datum = `${MES[Number(dm) - 1]} ${dy}`;

const CAPS = [
  [1, 7.5, `Slovenija ima ${D.n} občin – in v vsaki so stavbe drugačne.`],
  [8, 14.5, `Ponekod je pred letom 1981 nastalo ${D.pre[0]} % stanovanjske površine, drugod ${D.pre[1]} %.`],
  [16, 23, 'Stavbe se prenavljajo v vseh občinah – ponekod hitreje, drugod počasneje.'],
  [23.5, 30.5, `V ${D.sem['na poti']} občinah je prenova že na dobri poti, v večini drugih jo bo treba še pospešiti.`],
  [32, 38.5, `Tudi viri toplote so različni: obnovljivi viri pokrivajo od ${D.ove[0]} do ${D.ove[1]} % rabe energije v stavbah.`],
  [39, 45.5, 'Kjer so stavbe gosto skupaj, je smiselno daljinsko ogrevanje.'],
  [47, 54, `Primer: ${O4.name}. Kartica občine pokaže rabo energije, emisije, energente in energijske razrede.`],
  [54.5, 61.5, `${O4.name} prenovi okoli ${nf(O4.t_dej_pct, 1)} % stanovanjske površine na leto – ${tempo(O4)}.`],
  [63, 69.5, `Primer: ${O5.name}. Energetsko-podnebna kartica je izvleček za lokalni energetski koncept.`],
  [70, 76, `${O5.name}: obnovljivi viri pokrivajo ${nf(O5.vse.ove_pct.total, 0)} % rabe energije v stavbah, emisije na prebivalca so ${nf(O5.vse.tgp_t_preb.total, 1)} t (Slovenija ${nf(SIM.vse.tgp_t_preb.total, 1)} t).`],
  [77.5, 89.5, 'Poiščite svojo občino na strani Moja občina.'],
];
CAPS.forEach((c) => { c[2] = c[2].replace(/ %/g, ' %'); });
const SCENES = [[0, 15.5], [15.5, 31.5], [31.5, 46.5], [46.5, 62.5], [62.5, 77], [77, 90]];

// ---------------------------------------------------------------- zemljevid (SVG poti)
const pts = geo.features.flatMap((f) => (f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates).flat(1).flat(1));
const lon0 = Math.min(...pts.map((p) => p[0])), lon1 = Math.max(...pts.map((p) => p[0]));
const lat0 = Math.min(...pts.map((p) => p[1])), lat1 = Math.max(...pts.map((p) => p[1]));
const KX = Math.cos((46.1 * Math.PI) / 180), ASP = ((lon1 - lon0) * KX) / (lat1 - lat0);
const MAPW = 1000, MAPH = Math.round(MAPW / ASP);
const px = ([lo, la]) => [((lo - lon0) * KX) / ((lon1 - lon0) * KX) * MAPW, ((lat1 - la) / (lat1 - lat0)) * MAPH];
const mix = (a, b, t) => '#' + [0, 2, 4].map((i) => Math.round(parseInt(a.slice(1 + i, 3 + i), 16) * (1 - t) + parseInt(b.slice(1 + i, 3 + i), 16) * t).toString(16).padStart(2, '0')).join('');
const ramp = (stops, t) => { t = Math.max(0, Math.min(1, t)); const n = stops.length - 1, i = Math.min(n - 1, Math.floor(t * n)); return mix(stops[i], stops[i + 1], t * n - i); };
const PRE = ['#F5F2E8', '#F0AE2E', '#C4302C'], OVE = ['#E3F2DF', '#62B044', '#0B5E33'];
const SEM = { 'na poti': '#8FD19E', 'pod ciljem': '#E3B65C', 'ni podatka': '#6E7660' };
const shapes = geo.features.map((f) => {
  const m = byEid[f.properties.id];
  const polys = f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates;
  const d = polys.map((poly) => poly.map((ring) => 'M' + ring.map((p) => px(p).map((v) => v.toFixed(1)).join(',')).join('L') + 'Z').join('')).join('');
  const xs = polys.flat(2).map((p) => px(p)[0]);
  const cx = (Math.min(...xs) + Math.max(...xs)) / 2 / MAPW;
  return {
    d, cx: cx.toFixed(3),
    pre: m ? ramp(PRE, (m.pre1981_res_area_pct - D.pre[0]) / (D.pre[1] - D.pre[0])) : '#6E7660',
    sem: m ? SEM[m.t_semafor] || SEM['ni podatka'] : SEM['ni podatka'],
    ove: m && m.k_ove_pct != null ? ramp(OVE, (m.k_ove_pct - D.ove[0]) / (D.ove[1] - D.ove[0])) : '#6E7660',
  };
});
const svgMap = (id, key) => `<svg class="map" id="${id}" viewBox="-4 -4 ${MAPW + 8} ${MAPH + 8}">${shapes.map((s) => `<path d="${s.d}" data-cx="${s.cx}" data-f="${s[key]}"/>`).join('')}</svg>`;

// ---------------------------------------------------------------- HTML
const font = (p) => `data:font/woff2;base64,${readFileSync(resolve(root, 'node_modules/@fontsource-variable', p)).toString('base64')}`;
const CLS = ['A', 'B', 'C', 'D', 'E', 'F', 'G'];
const COL = { A: '#0B7A45', B: '#62B044', C: '#D9C92B', D: '#F0AE2E', E: '#EC842B', F: '#DE5A2B', G: '#C4302C' };
const housesCls = SI.segments.hise.classes_pct;  // ilustracija razredov (Slovenija, hiše), brez številk

function html(sq) {
  const W = sq ? 1080 : 1920, H = 1080, P = sq ? 70 : 120, inner = W - 2 * P;
  const mapW = sq ? 800 : 1000, mapH = Math.round(mapW / ASP), mapTop = sq ? 225 : 280, mapL = sq ? (W - 800) / 2 : P;
  const colL = sq ? P : P + mapW + 70, colW = sq ? inner : W - P - colL;
  const leg = (stops, a, b, si, unit) => `<div class="grad" style="background:linear-gradient(90deg,${stops.join(',')})"></div><div class="gl"><span>${a} ${unit}</span><span>Slovenija ${si} ${unit}</span><span>${b} ${unit}</span></div>`;
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
.sig { position: absolute; right: ${P}px; top: ${sq ? 30 : 92}px; font-size: ${sq ? 18 : 22}px; color: #DAD8C9; font-weight: 700; letter-spacing: .06em; }
.cap { position: absolute; left: 0; right: 0; bottom: 0; height: ${sq ? 150 : 120}px; background: rgba(0,0,0,.45); display: grid; place-items: center; font-size: ${sq ? 28 : 32}px; padding: 0 ${sq ? 60 : 140}px; text-align: center; line-height: 1.3; }
.prog { position: absolute; left: ${P}px; right: ${P}px; bottom: ${sq ? 160 : 132}px; display: flex; gap: 8px; }
.prog b { flex: 1; height: 4px; border-radius: 2px; background: rgba(245,242,232,.18); position: relative; overflow: hidden; }
.prog b i { position: absolute; inset: 0; background: #D6B25E; transform-origin: left; transform: scaleX(0); }
.map { position: absolute; left: ${mapL}px; top: ${mapTop}px; width: ${mapW}px; height: ${mapH}px; overflow: visible; }
.map path { fill: #48523A; stroke: #333D22; stroke-width: 1.2; stroke-linejoin: round; }
.col { position: absolute; left: ${colL}px; width: ${colW}px; top: ${sq ? mapTop + mapH + 22 : 300}px; }
.big { font-family: S; font-weight: 700; font-size: ${sq ? 0 : 120}px; line-height: 1; ${sq ? 'display:none;' : ''} }
.big small { display: block; font-family: M; font-size: 32px; color: #D6B25E; font-weight: 700; margin-top: 8px; }
.lg { font-size: ${sq ? 22 : 26}px; color: #DAD8C9; ${sq ? '' : 'margin-top: 40px;'} opacity: 0; }
.grad { height: ${sq ? 16 : 22}px; border-radius: 11px; margin: 6px 0; }
.gl { display: flex; justify-content: space-between; font-size: ${sq ? 19 : 22}px; color: #DAD8C9; }
.sw { display: ${sq ? 'inline-flex' : 'flex'}; align-items: center; gap: 12px; margin: ${sq ? '0 22px 0 0' : '12px 0'}; font-size: ${sq ? 21 : 28}px; }
.sw i { width: ${sq ? 20 : 26}px; height: ${sq ? 20 : 26}px; border-radius: 6px; display: inline-block; }
.sw b { font-family: S; font-size: ${sq ? 26 : 40}px; min-width: ${sq ? 0 : 70}px; }
.note { font-size: ${sq ? 17 : 21}px; color: #B9B7A8; line-height: 1.35; margin-top: ${sq ? 6 : 26}px; opacity: 0; }
.chip { background: rgba(245,242,232,.08); border: 2px solid rgba(214,178,94,.55); border-radius: 20px; padding: ${sq ? '12px 20px' : '20px 26px'}; margin-top: ${sq ? 8 : 26}px; opacity: 0; font-size: ${sq ? 20 : 25}px; color: #DAD8C9; line-height: 1.3; }
.chip b { display: block; font-family: S; font-size: ${sq ? 30 : 44}px; color: #F5F2E8; }
/* kartica občine (primer) */
.card { position: absolute; left: ${P}px; top: ${sq ? 230 : 270}px; width: ${inner}px; height: ${sq ? 640 : 630}px; background: #F5F2E8; border-radius: 22px; color: #333D22; padding: ${sq ? 24 : 32}px; display: grid; grid-template-columns: ${sq ? '1fr 1fr' : '1fr 1fr 1fr'}; grid-template-rows: auto; grid-auto-rows: 1fr; gap: ${sq ? 14 : 20}px; opacity: 0; }
.card .hd { grid-column: 1 / -1; display: flex; align-items: baseline; gap: 18px; flex-wrap: wrap; }
.card .hd b { font-family: S; font-size: ${sq ? 38 : 48}px; }
.card .hd span { font-size: ${sq ? 18 : 22}px; color: #6E7660; }
.tile { background: #FFFFFF; border: 2px solid #E4E0CF; border-radius: 16px; padding: ${sq ? '12px 14px' : '16px 20px'}; opacity: 0; display: flex; flex-direction: column; gap: ${sq ? 4 : 8}px; overflow: hidden; }
.tile h4 { font-size: ${sq ? 15 : 19}px; font-weight: 800; color: #4B5A3A; }
.tile .v { font-family: S; font-weight: 700; font-size: ${sq ? 30 : 52}px; line-height: 1.05; }
.tile .v small { font-family: M; font-size: ${sq ? 15 : 19}px; color: #6E7660; font-weight: 700; margin-left: 6px; }
.tile .s { font-size: ${sq ? 14 : 19}px; color: #6E7660; line-height: 1.3; }
.bar { display: flex; height: ${sq ? 16 : 22}px; border-radius: 6px; overflow: hidden; margin-top: 4px; }
.bar i { display: block; height: 100%; }
.bars { display: flex; align-items: flex-end; gap: ${sq ? 8 : 12}px; height: ${sq ? 64 : 92}px; margin-top: 4px; }
.bars span { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; height: 100%; font-size: ${sq ? 12 : 15}px; color: #6E7660; }
.bars i { display: block; width: 100%; background: #8F5A08; border-radius: 4px 4px 0 0; flex-shrink: 0; }
.bars { --bh: ${sq ? 38 : 60}px; }
.a4 .bars { --bh: ${sq ? 26 : 40}px; }
.bars b { font-size: ${sq ? 12 : 15}px; color: #333D22; }
.tile .pr { height: ${sq ? 12 : 16}px; border-radius: 8px; background: #E4E0CF; position: relative; margin-top: 6px; }
.tile .pr i { position: absolute; left: 0; top: 0; bottom: 0; border-radius: 8px; background: #1F7A57; }
.tile .pr u { position: absolute; top: -6px; bottom: -6px; width: 3px; background: #333D22; }
.dot { display: inline-block; width: .7em; height: .7em; border-radius: 50%; background: #8FD19E; margin-right: 6px; }
/* energetsko-podnebna kartica (primer, A4) */
.a4 { position: absolute; left: ${P}px; top: ${sq ? 230 : 262}px; width: ${sq ? 470 : 600}px; height: ${sq ? 640 : 660}px; background: #FFFFFF; border-radius: 10px; color: #333D22; padding: ${sq ? '20px 22px' : '26px 30px'}; opacity: 0; box-shadow: 0 18px 40px rgba(0,0,0,.35); }
.a4 .t { font-family: S; font-weight: 700; font-size: ${sq ? 22 : 28}px; line-height: 1.15; }
.a4 .s { font-size: ${sq ? 13 : 15}px; color: #6E7660; margin: 4px 0 8px; }
.a4 .sec { border-top: 2px solid #E4E0CF; padding-top: ${sq ? 6 : 8}px; margin-top: ${sq ? 6 : 10}px; opacity: 0; }
.a4 .sec h5 { font-size: ${sq ? 13 : 15}px; font-weight: 800; color: #1F7A57; margin-bottom: 4px; }
.a4 .row { display: flex; gap: ${sq ? 14 : 24}px; font-size: ${sq ? 13 : 15}px; color: #6E7660; }
.a4 .row b { display: block; font-family: S; font-size: ${sq ? 20 : 26}px; color: #333D22; }
.a4 .bar { height: ${sq ? 13 : 16}px; }
.a4 .lgd { font-size: ${sq ? 11 : 13}px; color: #6E7660; margin-top: 3px; }
.a4 .bars { height: ${sq ? 52 : 70}px; }
.a4 .bars span, .a4 .bars b { font-size: ${sq ? 11 : 13}px; }
.a4 .ft { position: absolute; left: ${sq ? 22 : 30}px; right: ${sq ? 22 : 30}px; bottom: 14px; font-size: 12px; color: #6E7660; display: flex; justify-content: space-between; }
.side { position: absolute; left: ${P + (sq ? 500 : 680)}px; right: ${P}px; top: ${sq ? 230 : 262}px; }
.side .chip { margin-top: 0; margin-bottom: ${sq ? 14 : 22}px; }
/* zaključek */
.btns { position: absolute; left: ${P}px; right: ${P}px; top: ${sq ? 330 : 340}px; display: grid; gap: 22px; justify-items: start; }
.btn { font-size: ${sq ? 38 : 48}px; font-weight: 800; padding: 18px 40px; border-radius: 999px; background: #D6B25E; color: #333D22; opacity: 0; }
.url { position: absolute; left: ${P}px; top: 720px; font-family: S; font-size: ${sq ? 42 : 64}px; font-weight: 700; opacity: 0; }
.fin { position: absolute; left: ${P}px; right: ${P}px; top: ${sq ? 790 : 820}px; font-size: ${sq ? 20 : 24}px; color: #DAD8C9; opacity: 0; }
.mus { position: absolute; left: ${P}px; right: ${P}px; top: ${sq ? 862 : 872}px; font-size: ${sq ? 17 : 19}px; color: #A9A797; opacity: 0; }
</style></head><body>
<p class="sig">IJS CEU · strokovne podlage NPS 2050 · osnutek, ${datum}</p>

<section class="sc" id="s1"><p class="k">Moja občina</p><h1>${D.n} občin, ${D.n} izhodišč</h1>
  ${svgMap('m1', 'pre')}
  <div class="col"><p class="big">${D.n}<small>občin</small></p>
    <div class="lg" id="l1">Stanovanjska površina, zgrajena pred letom 1981${leg(PRE, D.pre[0], D.pre[1], D.preSI, '%')}</div></div></section>

<section class="sc" id="s2"><p class="k">Prenova v občinah</p><h1>Kako hitro se prenavlja</h1>
  ${svgMap('m2', 'sem')}
  <div class="col"><div class="lg" id="l2">
    <p class="sw"><i style="background:${SEM['na poti']}"></i><b>${D.sem['na poti']}</b>na dobri poti</p>
    <p class="sw"><i style="background:${SEM['pod ciljem']}"></i><b>${D.sem['pod ciljem']}</b>tempo je treba povečati</p>
    <p class="sw"><i style="background:${SEM['ni podatka']}"></i><b>${D.sem['ni podatka']}</b>premalo podatkov</p></div>
    <p class="note" id="n2">Tempo prenove: delež stanovanjske površine na leto z vpisano obnovo fasade, strehe ali oken v katastru ali s spodbudo Eko sklada; v Sloveniji okoli ${nf(D.dej, 1)} %, za cilje NPS 2050 okoli ${nf(D.zah, 1)} %.</p></div></section>

<section class="sc" id="s3"><p class="k">Viri toplote</p><h1>Od kod toplota</h1>
  ${svgMap('m3', 'ove')}
  <div class="col"><div class="lg" id="l3">Delež obnovljivih virov v rabi energije v stavbah${leg(OVE, D.ove[0], D.ove[1], D.oveSI, '%')}</div>
    <div class="chip" id="c3"${sq ? ' style="display:none"' : ''}><b>${D.dh} %</b>potrebne toplote v Sloveniji je na območjih, kjer so stavbe dovolj gosto za daljinsko ogrevanje${sq ? '' : ` (v nekaterih občinah do ${D.dhMax} %)`}</div></div></section>

<section class="sc" id="s4"><p class="k">Kartica občine · primer</p><h1>Kaj najdete o svoji občini</h1>
  <div class="card" id="cd"><div class="hd"><b>${O4.name}</b><span>${nf(O4.pop)} prebivalcev · ${nf(O4.buildings)} stavb</span></div>
    <div class="tile"><h4>Raba energije v stavbah</h4><p class="v">${nf(O4.vse.fe_gwh.total)}<small>GWh na leto</small></p><p class="s">${nf(O4.vse.fe_mwh_preb.total, 1)} MWh na prebivalca · Slovenija ${nf(SIM.vse.fe_mwh_preb.total, 1)}</p></div>
    <div class="tile"><h4>Emisije toplogrednih plinov</h4><p class="v">${nf(O4.vse.tgp_kt.total)}<small>kt CO₂ ekv.</small></p><p class="s">${nf(O4.vse.tgp_t_preb.total, 1)} t na prebivalca · Slovenija ${nf(SIM.vse.tgp_t_preb.total, 1)}</p></div>
    <div class="tile"><h4>Energenti v stanovanjskih stavbah</h4><span class="bar">${Object.entries(O4.carriers_pct).filter(([, v]) => v > 0).map(([k, v]) => `<i style="background:${CAR[k][1]};width:${v}%"></i>`).join('')}</span><p class="s">${Object.entries(O4.carriers_pct).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([k, v]) => `${CAR[k][0]} ${nf(v, 0)} %`).join(' · ')}</p></div>
    <div class="tile"><h4>Energijski razredi stanovanjskih stavb</h4><span class="bar">${CLS.map((c) => `<i style="background:${COL[c]};width:${O4.nps_pct[c]}%"></i>`).join('')}</span><p class="s">od A do G · v razredih F in G ${nf(O4.nps_pct.F + O4.nps_pct.G, 0)} % površine</p></div>
    <div class="tile"><h4>Emisije do leta 2050, kt CO₂ ekv.</h4><div class="bars">${['2023', '2030', '2040', '2050'].map((y) => `<span><b>${nf(O4.pot[y].tgp_kt, O4.pot['2023'].tgp_kt < 100 ? 1 : 0)}</b><i style="height:calc(var(--bh) * ${(O4.pot[y].tgp_kt / O4.pot['2023'].tgp_kt).toFixed(3)})"></i>${y}</span>`).join('')}</div></div>
    <div class="tile"><h4>Tempo prenove stanovanjskih stavb</h4><p class="v">${nf(O4.t_dej_pct, 1)} %<small>na leto</small></p><div class="pr"><i style="width:${Math.min(100, 100 * O4.t_dej_pct / 3.2)}%"></i><u style="left:${100 * O4.t_zah_pct / 3.2}%"></u></div><p class="s"><span class="dot"></span>${O4.t_semafor === 'na poti' ? 'na dobri poti' : 'tempo je treba povečati'} · potrebno ${nf(O4.t_zah_pct, 1)} %</p></div>
  </div></section>

<section class="sc" id="s5"><p class="k">Za občinske službe · primer</p><h1>Energetsko-podnebna kartica</h1>
  <div class="a4" id="a4"><p class="t">Energetsko-podnebna kartica občine ${O5.name}</p><p class="s">stavbe · izvleček za lokalni energetski koncept</p>
    <div class="sec"><h5>Stanje 2023</h5><div class="row"><span><b>${nf(O5.vse.fe_gwh.total)} GWh</b>raba energije</span><span><b>${nf(O5.vse.tgp_kt.total, 1)} kt</b>emisije CO₂ ekv.</span><span><b>${nf(O5.vse.ove_pct.total, 0)} %</b>obnovljivi viri</span></div></div>
    <div class="sec"><h5>Energenti v stanovanjskih stavbah</h5><span class="bar">${Object.entries(O5.carriers_pct).filter(([, v]) => v > 0).map(([k, v]) => `<i style="background:${CAR[k][1]};width:${v}%"></i>`).join('')}</span><p class="lgd">${Object.entries(O5.carriers_pct).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([k, v]) => `${CAR[k][0]} ${nf(v, 0)} %`).join(' · ')}</p></div>
    <div class="sec"><h5>Pot do leta 2050 po scenariju NPS 2050: emisije, kt CO₂ ekv.</h5><div class="bars">${['2023', '2030', '2040', '2050'].map((y) => `<span><b>${nf(O5.pot[y].tgp_kt, O5.pot['2023'].tgp_kt < 100 ? 1 : 0)}</b><i style="height:calc(var(--bh) * ${(O5.pot[y].tgp_kt / O5.pot['2023'].tgp_kt).toFixed(3)})"></i>${y}</span>`).join('')}</div></div>
    <div class="sec"><h5>Energijski razredi stanovanjskih stavb</h5><span class="bar">${CLS.map((c) => `<i style="background:${COL[c]};width:${O5.nps_pct[c]}%"></i>`).join('')}</span><p class="lgd">od A do G · v razredih F in G ${nf(O5.nps_pct.F + O5.nps_pct.G, 0)} % površine</p></div>
    <div class="sec"><h5>Kaj to pomeni na leto (2026–2030)</h5><div class="row"><span><b>${nf(O5.stevilke.hise_leto)}</b>hiš</span><span><b>${nf(O5.stevilke.stanovanja_leto)}</b>stanovanj</span><span><b>${nf(O5.stevilke.nalozba_eur_leto / 1e6, 1)} mio €</b>naložb</span></div></div>
    <p class="ft"><span>IJS CEU · strokovne podlage NPS 2050</span><span>CC BY-NC-ND</span></p></div>
  <div class="side">
    <div class="chip"><b>${nf(O5.vse.ove_pct.total, 0)} %</b>obnovljivih virov v rabi energije v stavbah (Slovenija ${nf(SIM.vse.ove_pct.total, 0)} %)</div>
    <div class="chip"><b>${nf(O5.vse.tgp_t_preb.total, 1)} t</b>CO₂ ekv. na prebivalca (Slovenija ${nf(SIM.vse.tgp_t_preb.total, 1)} t)</div>
    <div class="chip"><b>${nf(TOPC5[1], 0)} %</b>rabe energije v stanovanjskih stavbah pokrije ${CAR[TOPC5[0]][0]}</div></section>

<section class="sc" id="s6"><p class="k">Kje najdete več</p><h1>Moja občina</h1>
  <div class="btns"><span class="btn">Kartica vaše občine</span><span class="btn">Primerjava občin</span><span class="btn">Energetsko-podnebna kartica</span></div>
  <p class="url">ijs-ceu.github.io/nps2050/moja-obcina</p>
  <p class="fin">Ocene IJS CEU za stavbe v občinah iz katastra, energetskih izkaznic, Eko sklada in toplotne karte, usklajene z energetsko bilanco.</p>
  ${process.env.MUSIC_CREDIT ? `<p class="mus">Glasba: ${process.env.MUSIC_CREDIT}</p>` : ''}</section>

<div class="prog">${SCENES.map(() => '<b><i></i></b>').join('')}</div>
<div class="cap"><span id="cap"></span></div>
<script>
const SC = ${JSON.stringify(SCENES)}, CAPS = ${JSON.stringify(CAPS)};
const cl = (x) => Math.max(0, Math.min(1, x)), ease = (x) => { x = cl(x); return x < .5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2; };
const $ = (s) => document.querySelector(s), $$ = (s) => [...document.querySelectorAll(s)];
const fadeUp = (el, t, t0, d = .8) => { if (!el) return; const p = ease((t - t0) / d); el.style.opacity = p; el.style.transform = 'translateY(' + (1 - p) * 24 + 'px)'; };
const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
const paint = (id, t, t0, dur) => $$('#' + id + ' path').forEach((p) => { const k = cl((t - t0 - p.dataset.cx * dur) / 0.6);
  const a = hex('#48523a'), b = hex(p.dataset.f); p.style.fill = 'rgb(' + a.map((v, i) => Math.round(v + (b[i] - v) * k)).join(',') + ')'; });
window.render = (t) => {
  SC.forEach(([a, b], i) => { const el = $('#s' + (i + 1)); const o = Math.min(cl((t - a) / .7), i === SC.length - 1 ? 1 : cl((b - t) / .7)); el.style.opacity = o; el.style.visibility = o > 0 ? 'visible' : 'hidden';
    $$('.prog i')[i].style.transform = 'scaleX(' + cl((t - a) / (b - a)) + ')'; });
  const c = CAPS.find(([a, b]) => t >= a && t <= b); const cap = $('#cap'); cap.textContent = c ? c[2] : '';
  cap.style.opacity = c ? Math.min(cl((t - c[0]) / .4), cl((c[1] - t) / .4)) : 0;
  // 1–3: zemljevidi se obarvajo od zahoda proti vzhodu
  paint('m1', t, 1.5, 3); fadeUp($('#l1'), t, 5); fadeUp($('#s1 .big'), t, 1);
  paint('m2', t, 17, 3.5); fadeUp($('#l2'), t, 20); fadeUp($('#n2'), t, 24);
  paint('m3', t, 33, 3); fadeUp($('#l3'), t, 36); fadeUp($('#c3'), t, 39.5);
  // 4: kartica občine
  fadeUp($('#cd'), t, 47.5); $$('#cd .tile').forEach((x, i) => fadeUp(x, t, 48.8 + i * 1.4));
  // 5: energetsko-podnebna kartica
  fadeUp($('#a4'), t, 63.5); $$('#a4 .sec').forEach((x, i) => fadeUp(x, t, 64.8 + i * 1)); $$('.side .chip').forEach((x, i) => fadeUp(x, t, 66.5 + i * 2.2));
  // 6
  $$('.btn').forEach((x, i) => fadeUp(x, t, 78.5 + i * .9)); fadeUp($('.url'), t, 82); fadeUp($('.fin'), t, 83.5);
  const mu = $('.mus'); if (mu) mu.style.opacity = cl((t - 85) / 1);
};
render(0);
</script></body></html>`;
}

// ---------------------------------------------------------------- izris in sestava
const out = resolve(root, 'public/mediji'); mkdirSync(out, { recursive: true });
const tmp = resolve(root, 'tests/_video_obcine_frames'); rmSync(tmp, { recursive: true, force: true }); mkdirSync(tmp, { recursive: true });
const ts = (s) => { const m = Math.floor(s / 60) % 60, x = (s % 60).toFixed(3).padStart(6, '0'); return `00:${String(m).padStart(2, '0')}:${x}`; };
writeFileSync(resolve(out, `${NAME}.vtt`), 'WEBVTT\n\n' + CAPS.map(([a, b, s], i) => `${i + 1}\n${ts(a)} --> ${ts(b)}\n${s}\n`).join('\n'), 'utf-8');

const audio = resolve(tmp, 'podlaga.wav');
const expr = ['110', '164.81', '220', '277.18'].map((f, i) => `0.035*sin(2*PI*${f}*t)*(0.65+0.35*sin(2*PI*${(0.05 + i * 0.013).toFixed(3)}*t))`).join('+');
if (process.env.MUSIC) execFileSync(FFMPEG, ['-y', '-loglevel', 'error', '-ss', process.env.MUSIC_START || '1', '-t', String(DUR), '-i', process.env.MUSIC,
  '-af', `afade=t=in:d=1.5,afade=t=out:st=${DUR - 4.5}:d=4.5,loudnorm=I=-20:TP=-2:LRA=11`, '-ar', '48000', audio]);
else execFileSync(FFMPEG, ['-y', '-loglevel', 'error', '-f', 'lavfi', '-i', `aevalsrc=${expr}:s=48000:d=${DUR}`, '-af', `lowpass=f=1200,afade=t=in:d=3,afade=t=out:st=${DUR - 4}:d=4`, audio]);

const browser = await chromium.launch();
if (process.env.STILLS) {
  for (const sq of [false, true]) {
    const page = await browser.newPage({ viewport: { width: sq ? 1080 : 1920, height: 1080 } });
    await page.setContent(html(sq), { waitUntil: 'load' }); await page.evaluate(() => document.fonts.ready);
    for (const t of process.env.STILLS.split(',').map(Number)) { await page.evaluate((x) => window.render(x), t); await page.screenshot({ path: resolve(root, `tests/_vob_${sq ? 'k' : 'w'}${t}.png`) }); }
  }
  await browser.close(); rmSync(tmp, { recursive: true, force: true }); process.exit(0);
}
for (const [sq, name] of [[false, NAME], [true, `${NAME}-kvadrat`]]) {
  const page = await browser.newPage({ viewport: { width: sq ? 1080 : 1920, height: 1080 } });
  await page.setContent(html(sq), { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready);
  const dir = resolve(tmp, name); mkdirSync(dir);
  for (let f = 0; f < FPS * DUR; f++) {
    await page.evaluate((t) => window.render(t), f / FPS);
    await page.screenshot({ path: resolve(dir, `f${String(f).padStart(5, '0')}.jpg`), type: 'jpeg', quality: 92 });
  }
  if (!sq) { await page.evaluate((t) => window.render(t), 28); await page.screenshot({ path: resolve(out, `${NAME}-poster.jpg`), type: 'jpeg', quality: 85 }); }
  await page.close();
  execFileSync(FFMPEG, ['-y', '-loglevel', 'error', '-framerate', String(FPS), '-i', resolve(dir, 'f%05d.jpg'), '-i', audio,
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '23', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', process.env.MUSIC ? '160k' : '96k', '-shortest', '-movflags', '+faststart',
    resolve(out, `${name}.mp4`)]);
  console.log(`public/mediji/${name}.mp4`);
}
await browser.close();
rmSync(tmp, { recursive: true, force: true });
