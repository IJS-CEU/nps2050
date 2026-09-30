/** Rubrike strani (navodila projekta §3). Stran je samo v slovenščini. */
export const pages = [
  { id: 'domov', slug: '' },
  { id: 'kaj-je-nps', slug: 'kaj-je-nps-2050' },
  { id: 'lastniki', slug: 'za-lastnike' },
  { id: 'obcine', slug: 'moja-obcina' },
  { id: 'strokovne-podlage', slug: 'strokovne-podlage' },
  { id: 'ukrepi', slug: 'ukrepi-in-financiranje' },
  { id: 'spremljanje', slug: 'spremljanje' },
  { id: 'javna-obravnava', slug: 'javna-obravnava' },
  { id: 'dokumenti', slug: 'dokumenti' },
  // Podstrani zunaj glavne navigacije
  { id: 'preveri', slug: 'preveri-stavbo' },
  { id: 'mediji', slug: 'za-medije' },
  { id: 'revscina', slug: 'energetska-revscina' },
  { id: 'slovar', slug: 'slovar-izrazov' },
  { id: 'primerjava', slug: 'primerjava-obcin' },
] as const;

export type PageId = (typeof pages)[number]['id'];
export const pageIds = pages.map((p) => p.id) as [PageId, ...PageId[]];

/** Pot z upoštevanim `base` (deluje na GitHub Pages v podmapi in na lastni domeni). */
export function withBase(path: string): string {
  const b = import.meta.env.BASE_URL;
  return (b.endsWith('/') ? b : b + '/') + path.replace(/^\//, '');
}

export function pageUrl(id: PageId): string {
  const s = pages.find((x) => x.id === id)!.slug;
  return withBase(s ? s + '/' : '');
}
