/** Nalaganje JSON iz public/data/ v brskalniku (upošteva `base`). Brez ECharts, da ga lahko uporabijo tudi strani brez grafov. */
export async function loadJson<T>(name: string): Promise<T> {
  const b = import.meta.env.BASE_URL;
  const res = await fetch(`${b.endsWith('/') ? b : b + '/'}data/${name}.json`);
  if (!res.ok) throw new Error(`${name}.json: ${res.status}`);
  return res.json() as Promise<T>;
}
