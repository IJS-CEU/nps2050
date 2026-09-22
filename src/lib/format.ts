/** Slovenski zapis števil: 1.149,4 (piko za tisočice doda Intl šele od 10.000 naprej, zato jo dodamo sami). */
export function nf(v: number | null | undefined, decimals?: number): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '–';
  const d = decimals ?? (Number.isInteger(v) ? 0 : Math.min(2, (String(v).split('.')[1] || '').length));
  const [int, frac] = Math.abs(v).toFixed(d).split('.');
  const grouped = int.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  return (v < 0 ? '−' : '') + grouped + (frac ? ',' + frac : '');
}

export function esc(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!);
}
