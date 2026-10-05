"""Preglednice iz osnutka NPS_vNN.docx, poiskane po besedilu napisa (številke preglednic se med različicami premikajo)."""
import re
from datetime import date, datetime
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

W_T = qn('w:t')


def _text(el) -> str:
    # Vse w:t pod elementom, tudi v hiperpovezavah, poljih in vstavljenih spremembah (w:ins);
    # izbrisano besedilo je v w:delText in se ne bere. paragraph.text bi del besedila izpustil.
    txt = ''.join(t.text or '' for t in el.iter(W_T)).strip()
    # Wordov samodejni popravek spremeni oznake točk »(c)« in »(r)« v © in ® (npr. »čl. 17(14)©«) – vrnemo izvirnik.
    return txt.replace('©', '(c)').replace('®', '(r)')


class Draft:
    def __init__(self, path: Path):
        self.path = path
        self.name = path.stem  # npr. NPS_v38
        self.doc = Document(str(path))
        self._tables: list[tuple[str | None, list[list[str]]]] = []
        self._index()

    @property
    def date(self) -> date:
        # Kasnejši od datuma v lastnostih dokumenta in datuma spremembe datoteke (nekatera orodja lastnosti ne posodobijo).
        ft = datetime.fromtimestamp(self.path.stat().st_mtime).date()
        mod = self.doc.core_properties.modified
        return max(mod.date(), ft) if isinstance(mod, datetime) else ft

    def _index(self):
        caption = None
        for el in self.doc.element.body.iterchildren():
            if el.tag == qn('w:p'):
                style = el.find(qn('w:pPr'))
                sid = style.find(qn('w:pStyle')).get(qn('w:val')) if style is not None and style.find(qn('w:pStyle')) is not None else ''
                txt = _text(el)
                if txt and self._is_caption(sid):
                    caption = txt
            elif el.tag == qn('w:tbl'):
                self._tables.append((caption, self._rows(el)))
                caption = None

    def _is_caption(self, style_id: str) -> bool:
        s = self.doc.styles
        try:
            name = s.get_by_id(style_id, 1).name if style_id else ''
        except Exception:
            name = style_id
        return name in ('Caption', 'caption') or name.startswith('Napis')

    @staticmethod
    def _rows(tbl) -> list[list[str]]:
        rows = []
        for tr in tbl.iter(qn('w:tr')):
            cells = []
            for tc in tr.iter(qn('w:tc')):
                # Vodoravno spojene celice (gridSpan) štejejo enkrat, kot v Wordu.
                # Odstavki v celici (npr. »≤ 226« in »217«) se ločijo z » / «.
                paras = [_text(p) for p in tc.iter(qn('w:p'))]
                cells.append(' / '.join(x for x in paras if x))
            rows.append(cells)
        return rows

    def table(self, caption_pattern: str) -> list[list[str]]:
        hits = [rows for cap, rows in self._tables if cap and re.search(caption_pattern, cap)]
        if len(hits) != 1:
            raise LookupError(f'{self.name}: preglednica z napisom /{caption_pattern}/ – {len(hits)} zadetkov (pričakovan 1)')
        return hits[0]


def row(rows: list[list[str]], label_pattern: str) -> list[str]:
    """Prva vrstica, katere prva celica ustreza vzorcu."""
    for r in rows:
        if r and re.search(label_pattern, r[0]):
            return r
    raise LookupError(f'vrstica /{label_pattern}/ ni najdena (prve celice: {[r[0] for r in rows if r][:12]})')


def latest_draft(folder: Path, pattern: str) -> Path:
    found = []
    for p in folder.iterdir():
        m = re.match(pattern, p.name)
        if m and p.is_file():
            found.append((int(m.group(1)), p))
    if not found:
        raise FileNotFoundError(f'v {folder} ni datoteke /{pattern}/')
    return max(found)[1]
