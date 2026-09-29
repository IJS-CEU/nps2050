/**
 * Skupno jedro grafov: ECharts (samo potrebni moduli, izris v SVG), barve iz CSS žetonov,
 * ponovni izris ob menjavi teme, nalaganje JSON pod `base` ter prenos PNG in SVG.
 */
import * as echarts from 'echarts/core';
import { BarChart, LineChart, SankeyChart, ScatterChart } from 'echarts/charts';
import { GraphicComponent, GridComponent, LegendComponent, TooltipComponent } from 'echarts/components';
import { LabelLayout } from 'echarts/features';
import { SVGRenderer } from 'echarts/renderers';
import { esc, nf } from '../../lib/format';

echarts.use([BarChart, LineChart, SankeyChart, ScatterChart, GraphicComponent, GridComponent, LegendComponent, TooltipComponent, LabelLayout, SVGRenderer]);

export { echarts, esc, nf };
export type Option = echarts.EChartsCoreOption;

export interface Tokens {
  /** Širina grafa v px – za prilagoditev ozkim zaslonom (legenda v več vrsticah). */
  width: number; narrow: boolean;
  panel: string; ink: string; ink2: string; muted: string; line: string; grid: string; axis: string;
  s: Record<string, string>;
  font: string;
}

export function tokens(width = 800): Tokens {
  const cs = getComputedStyle(document.documentElement);
  const v = (n: string) => cs.getPropertyValue(n).trim();
  const s: Record<string, string> = {};
  for (const k of ['enodruzinske', 'vecstanovanjske', 'javne', 'zasebne', 's0', 's1', 's2', 'info', 'ref']) s[k] = v(`--s-${k}`);
  return {
    width, narrow: width < 560,
    panel: v('--panel'), ink: v('--ink'), ink2: v('--ink2'), muted: v('--chart-muted'), line: v('--line'),
    grid: v('--chart-grid'), axis: v('--chart-axis'), s,
    font: "'Manrope Variable', system-ui, -apple-system, 'Segoe UI', sans-serif",
  };
}

export async function loadJson<T>(name: string): Promise<T> {
  const b = import.meta.env.BASE_URL;
  const res = await fetch(`${b.endsWith('/') ? b : b + '/'}data/${name}.json`);
  if (!res.ok) throw new Error(`${name}.json: ${res.status}`);
  return res.json() as Promise<T>;
}

const reduceMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/** Skupne nastavitve: tanke oznake, tihe osi in mreža, besedilo v barvah besedila (ne serij). */
export function base(t: Tokens): Option {
  return {
    backgroundColor: 'transparent',
    animation: !reduceMotion(),
    animationDuration: 400,
    textStyle: { fontFamily: t.font, color: t.ink2, fontSize: 12 },
    grid: { left: 8, right: 16, top: t.narrow ? 84 : 52, bottom: 8, containLabel: true },
    legend: {
      top: 0, left: 0, itemGap: 16, itemWidth: 14, itemHeight: 10,
      textStyle: { color: t.ink2, fontSize: 12, fontFamily: t.font },
      inactiveColor: t.axis,
    },
    tooltip: {
      backgroundColor: t.panel, borderColor: t.line, borderWidth: 1, padding: [8, 10],
      textStyle: { color: t.ink, fontFamily: t.font, fontSize: 12 },
      extraCssText: 'box-shadow:0 4px 16px rgba(0,0,0,.12);border-radius:8px;',
      confine: true,
    },
  };
}

export function valueAxis(t: Tokens, extra: Record<string, unknown> = {}) {
  return {
    type: 'value',
    axisLine: { show: false }, axisTick: { show: false },
    splitLine: { lineStyle: { color: t.grid, width: 1 } },
    axisLabel: { color: t.muted, formatter: (v: number) => nf(v) },
    nameTextStyle: { color: t.muted, align: 'left' },
    ...extra,
  };
}

export function yearAxis(t: Tokens, extra: Record<string, unknown> = {}) {
  return {
    axisLine: { lineStyle: { color: t.axis } }, axisTick: { show: false },
    axisLabel: { color: t.muted, formatter: (v: number | string) => String(v) },
    splitLine: { show: false },
    ...extra,
  };
}

/** Vrstica v opisu: vrednost je poudarjena, ime serije sledi; ključ je kratka črta v barvi serije. */
export function tipRow(color: string, name: string, value: string, key: 'line' | 'rect' = 'line') {
  const sw = key === 'line'
    ? `<span style="display:inline-block;width:12px;height:2px;background:${color};vertical-align:middle;margin-right:6px"></span>`
    : `<span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:${color};vertical-align:middle;margin-right:6px"></span>`;
  return `<div style="display:flex;gap:10px;justify-content:space-between;align-items:center"><span>${sw}<span style="opacity:.8">${esc(name)}</span></span><b>${esc(value)}</b></div>`;
}

export function tipTitle(s: string) {
  return `<div style="font-weight:700;margin-bottom:4px">${esc(s)}</div>`;
}

export interface Mounted { chart: echarts.ECharts; redraw: () => void }

/** Poveže graf s figuro: izris, ponovni izris ob temi in velikosti, gumba za prenos. */
export function mount(fig: HTMLElement, render: (t: Tokens) => Option, canvas?: HTMLElement): Mounted {
  const el = canvas ?? (fig.querySelector('.chart-canvas') as HTMLElement);
  const chart = echarts.init(el, null, { renderer: 'svg' });
  let narrow: boolean | null = null;
  const redraw = () => {
    const t = tokens(el.clientWidth || 800);
    narrow = t.narrow;
    chart.setOption(render(t), { notMerge: true });
  };
  redraw();
  window.addEventListener('nps-theme', redraw);
  new ResizeObserver(() => {
    chart.resize();
    if ((el.clientWidth < 560) !== narrow) redraw();
  }).observe(el);
  if (!canvas) {
    const name = fig.dataset.file || 'graf';
    fig.querySelector('[data-dl="svg"]')?.addEventListener('click', () => downloadSvg(chart, fig, name));
    fig.querySelector('[data-dl="png"]')?.addEventListener('click', () => downloadPng(chart, fig, name));
  }
  el.classList.add('ready');
  return { chart, redraw };
}

/** Izvoz za prenos: graf z naslovom zgoraj in virom spodaj, na ozadju plošče (slika mora biti razumljiva sama zase). */
function exportSvg(chart: echarts.ECharts, fig: HTMLElement): { svg: string; w: number; h: number } {
  const inner = (chart as unknown as { renderToSVGString: () => string }).renderToSVGString();
  const t = tokens();
  const w = chart.getWidth(), ch = chart.getHeight();
  // Naslov + trenutne izbire (npr. »Primerjava S0–S2, Končna energija«), da je slika razumljiva sama zase.
  const picked = [...fig.querySelectorAll<HTMLInputElement>('.chart-controls input:checked')]
    .filter((i) => !i.closest('[hidden]'))
    .map((i) => fig.querySelector(`label[for="${i.id}"]`)?.textContent?.trim())
    .filter(Boolean);
  const title = [fig.querySelector('h3')?.textContent?.trim() ?? '', picked.join(', ')].filter(Boolean).join(' – ');
  const source = [...fig.querySelectorAll<HTMLElement>('.chart-cap p')].map((p) => p.textContent?.trim() ?? '').find((x) => x.startsWith('Vir:')) ?? '';
  const top = 40, bottom = 30, h = ch + top + bottom;
  const font = `font-family="${esc(t.font)}"`;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">`
    + `<rect width="100%" height="100%" fill="${t.panel}"/>`
    + `<text x="8" y="24" ${font} font-size="16" font-weight="700" fill="${t.ink}">${esc(title)}</text>`
    + inner.replace(/<svg([^>]*)>/, `<svg$1 x="0" y="${top}">`)
    + `<text x="8" y="${h - 10}" ${font} font-size="11" fill="${t.ink2}">${esc(source)} · Strokovne podlage NPS 2050, IJS CEU · CC BY 4.0</text>`
    + `</svg>`;
  return { svg, w, h };
}

function save(blob: Blob, filename: string) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

function downloadSvg(chart: echarts.ECharts, fig: HTMLElement, name: string) {
  save(new Blob([exportSvg(chart, fig).svg], { type: 'image/svg+xml' }), `${name}.svg`);
}

function downloadPng(chart: echarts.ECharts, fig: HTMLElement, name: string) {
  const { svg, w, h } = exportSvg(chart, fig);
  const scale = 2;
  const img = new Image();
  img.onload = () => {
    const c = document.createElement('canvas');
    c.width = w * scale; c.height = h * scale;
    const ctx = c.getContext('2d')!;
    ctx.scale(scale, scale);
    ctx.drawImage(img, 0, 0, w, h);
    c.toBlob((b) => b && save(b, `${name}.png`), 'image/png');
  };
  img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
}

/** Skupina izbirnih gumbov (radio) → trenutna vrednost in poslušalec sprememb. */
export function choice(fig: HTMLElement, name: string, onChange: (v: string) => void): () => string {
  const inputs = [...fig.querySelectorAll<HTMLInputElement>(`input[name="${name}"]`)];
  inputs.forEach((i) => i.addEventListener('change', () => i.checked && onChange(i.value)));
  return () => inputs.find((i) => i.checked)?.value ?? inputs[0]?.value ?? '';
}
