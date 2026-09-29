/**
 * Vtičnik za MDX (procesor Sätteri, privzet v Astro 7): prvo pojavitev vsakega izraza iz slovarja na strani
 * oblikuje kot povezavo na slovar z razlago v data-def (oblaček prikaže TermPop.astro; brez JS je to navadna povezava).
 * Preskoči naslove, povezave, <summary>, kodo in komponente (JSX z veliko začetnico) ter stran slovarja samo.
 */
import type { HastPluginEntry, PluginFactoryContext } from 'satteri';
import { izrazi } from './slovar';

interface Node { type: string; value?: string; tagName?: string; name?: string | null; children?: Node[] }

const SKIP_TAGS = new Set(['a', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'summary', 'code', 'pre', 'abbr', 'button', 'label', 'caption', 'th', 'figcaption']);
const B = '(?<![\\p{L}\\p{N}])';
const E = '(?![\\p{L}\\p{N}])';
const compiled = izrazi.map((t) => ({ t, re: new RegExp(`${B}(?:${t.re})${E}`, t.cs ? 'u' : 'iu') }));

export default function izraziPlugin(opts: { base: string; slug: string }): HastPluginEntry {
  const href = (id: string) => `${opts.base.replace(/\/?$/, '/')}${opts.slug}/#${id}`;
  return (fctx: PluginFactoryContext) => {
    if (fctx.fileURL && /[\\/]slovar\.mdx$/.test(decodeURIComponent(fctx.fileURL.pathname))) return null;
    const used = new Set<string>(); // na datoteko (stran): vsak izraz se označi le enkrat

    const split = (text: string): Node[] | null => {
      let best: { i: number; len: number; t: (typeof izrazi)[number] } | null = null;
      for (const { t, re } of compiled) {
        if (used.has(t.id)) continue;
        const m = re.exec(text);
        if (m && (!best || m.index < best.i)) best = { i: m.index, len: m[0].length, t };
      }
      if (!best) return null;
      used.add(best.t.id);
      const out: Node[] = [];
      if (best.i > 0) out.push({ type: 'text', value: text.slice(0, best.i) });
      out.push({
        type: 'element', tagName: 'a',
        properties: { className: ['term'], href: href(best.t.id), dataDef: best.t.def, dataTerm: best.t.term },
        children: [{ type: 'text', value: text.slice(best.i, best.i + best.len) }],
      } as Node);
      const rest = text.slice(best.i + best.len);
      if (rest) out.push(...(split(rest) ?? [{ type: 'text', value: rest }]));
      return out;
    };

    return {
      name: 'nps-izrazi',
      text(node, ctx) {
        if (!node.value || used.size === compiled.length) return;
        // Preskoči besedilo v prepovedanih elementih in v komponentah.
        for (let p = ctx.parent(node) as Node | undefined; p && p.type !== 'root'; p = ctx.parent(p as never) as Node | undefined) {
          if (p.type === 'element' && SKIP_TAGS.has(p.tagName!)) return;
          if ((p.type === 'mdxJsxFlowElement' || p.type === 'mdxJsxTextElement') && (!p.name || /^[A-Z]/.test(p.name) || SKIP_TAGS.has(p.name))) return;
        }
        const parts = split(node.value);
        if (parts) ctx.replaceNode(node, parts as never);
      },
    };
  };
}
