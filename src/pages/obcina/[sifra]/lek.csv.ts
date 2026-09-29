/** CSV za lokalni energetski koncept (LEK) za eno občino; podpisano kot intelektualna lastnina IJS CEU. */
import type { APIRoute } from 'astro';
import { loadData, type ObcineIndex } from '../../../lib/data';
import { LEK_SIGN, lekData, lekRows } from '../../../lib/lek';

export function getStaticPaths() {
  return loadData<ObcineIndex>('obcine_index').municipalities.map((m) => ({ params: { sifra: String(m.sifra) } }));
}

const cell = (v: unknown) => {
  if (v === null || v === undefined) return '';
  const s = typeof v === 'number' ? String(v).replace('.', ',') : String(v);
  return /[;"\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

export const GET: APIRoute = ({ params }) => {
  const sifra = String(params.sifra);
  const { o, draftDate } = lekData(sifra);
  const lines = [
    `Strokovne podlage NPS 2050 – izvleček za lokalni energetski koncept;Občina ${o.name}`,
    `${LEK_SIGN};`,
    `Podatki: osnutek NPS 2050 z dne ${draftDate}, kataster nepremičnin, register energetskih izkaznic, Eko sklad, energetsko knjigovodstvo, model IJS CEU. Ocene modela so označene.;`,
    '',
    'Kazalnik;Enota;Občina;Slovenija',
    ...lekRows(sifra).map((r) => r.map(cell).join(';')),
  ];
  return new Response('﻿' + lines.join('\r\n') + '\r\n', { headers: { 'Content-Type': 'text/csv; charset=utf-8' } });
};
