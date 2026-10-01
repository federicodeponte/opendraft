#!/usr/bin/env python3
"""The journal template: a compiled draft typeset as a two-column journal article.

Standard library only; shells out to pandoc for markdown and to weasyprint for
the PDF, exactly as export.py does. Called by `export.py --template journal`,
normally run through export.py. Run directly it writes the HTML page only:

    journal.py final.md -o page.html [--figures research/figures] [--research research]

What it adds over pandoc's default page:

- a masthead with a brand line (default "OpenDraft") and nothing invented: no
  journal name, volume, issue, received date or affiliation the draft does not
  state;
- a serif title with the subtitle split off at the first ": ";
- the abstract in two columns, and an optional at-a-glance strip whose every
  number is read from research/index.json and research/sources.json;
- numbered sections, a two-column body, merged adjacent author-year citations;
- the evidence figures, tables and equations, placed where the draft has a
  placeholder line for them:

    {figure:evidence-profile}   {figure:evidence-map}   {figure:source-flow}
    {table:studies}             {table:ledger}          {equations:evidence-index}

A placeholder whose file `evidence.py figures` did not produce is an error,
never a silent gap. A `{figure:evidence-profile}` placed before the first
section heading becomes the page-one hero figure under the abstract.
"""
import argparse
import html
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / "assets"
FONT_DIR = ASSETS / "fonts"
EQUATION_FILES = ("equation-1.svg", "equation-2.svg", "equation-3.svg")

PLACEHOLDER = re.compile(r"^\{(figure|table|equations):([a-z0-9-]+)\}\s*$")
SLOTS = {
    ("figure", "evidence-profile"): ("evidence-profile.svg", "evidence-profile", "figure"),
    ("figure", "evidence-map"): ("evidence-map.svg", "evidence-map", "figure"),
    ("figure", "source-flow"): ("source-flow.svg", "source-flow", "figure"),
    ("table", "studies"): ("table-studies.html", "studies", "table"),
    ("table", "ledger"): ("table-ledger.html", "ledger", "table"),
    ("equations", "evidence-index"): (None, None, "equations"),
}
ABSTRACT_NAMES = ("abstract", "zusammenfassung", "resumen", "résumé", "resume", "summary")
REFERENCE_NAMES = ("references", "bibliography", "literaturverzeichnis", "literatur",
                   "referencias", "bibliografía", "références", "bibliographie")
ADJACENT_CITES = re.compile(r"(\d{4}[a-z]?|n\.d\.)\) \((?=[A-ZÀ-ÖØ-Ý])")

FONTS = [
    ("STIX Two Text", "STIX-400.ttf", 400, "normal"),
    ("STIX Two Text", "STIX-600.ttf", 600, "normal"),
    ("STIX Two Text", "STIX-700.ttf", 700, "normal"),
    ("STIX Two Text", "STIXi-400.ttf", 400, "italic"),
    ("STIX Two Text", "STIXi-600.ttf", 600, "italic"),
    ("STIXGeneral", "STIX-400.ttf", 400, "normal"),
    ("STIXGeneral", "STIXi-400.ttf", 400, "italic"),
    ("Source Sans 3", "SS-400.ttf", 400, "normal"),
    ("Source Sans 3", "SS-600.ttf", 600, "normal"),
    ("Source Sans 3", "SS-700.ttf", 700, "normal"),
    ("Source Sans 3", "SSi-400.ttf", 400, "italic"),
]


class JournalError(Exception):
    pass


def font_faces(font_dir=FONT_DIR):
    """@font-face rules for every bundled font file that is present, and the
    list of files that are not. A missing file degrades to the fallback stack
    named in the CSS; it is reported, not fatal."""
    rules, missing = [], []
    for family, name, weight, style in FONTS:
        path = Path(font_dir) / name
        if path.exists():
            rules.append(f'@font-face{{font-family:"{family}";src:url("{path.as_uri()}");'
                         f"font-weight:{weight};font-style:{style}}}")
        elif name not in missing:
            missing.append(name)
    return "\n".join(rules), missing


CSS = """
@page{size:A4;margin:17mm 16mm 18mm;
  @top-left{content:string(runhead);font:italic 8pt var(--serif);color:#59626b}
  @top-right{content:string(brand);font:600 7.5pt var(--sans);color:#59626b}
  @bottom-center{content:counter(page);font:7.5pt var(--sans);color:#59626b}}
@page:first{@top-left{content:none}@top-right{content:none}}
:root{--serif:"STIX Two Text",STIXGeneral,Charter,Georgia,"Times New Roman",serif;
  --sans:"Source Sans 3","Source Sans Pro","Helvetica Neue",Arial,sans-serif;--accent:#1d6b60}
html{font-family:var(--serif);font-size:9.3pt;line-height:1.38;color:#181c20;hyphens:auto;
  font-variant-numeric:lining-nums}
body{margin:0}
.mast{display:flex;justify-content:space-between;align-items:baseline;
  border-bottom:.6pt solid #181c20;padding-bottom:3pt}
.mast .brand{font:600 12.5pt var(--serif);letter-spacing:.01em;string-set:brand content()}
.mast .meta{font:7.6pt var(--sans);color:#59626b}
.kind{font:600 8pt var(--sans);color:var(--accent);margin:14pt 0 5pt}
.spacer{height:14pt}
h1{string-set:runhead content();font:600 22pt/1.1 var(--serif);letter-spacing:-.005em;margin:0 0 5pt;color:#101316}
.subtitle{font:italic 13pt/1.25 var(--serif);color:#3d464f;margin:0 0 10pt}
.byline{font:8.3pt/1.4 var(--sans);color:#3d464f;margin:0 0 12pt}
.abstract{border-top:.6pt solid #181c20;border-bottom:.6pt solid #b9c0c6;padding:8pt 0 6pt;
  column-count:2;column-gap:6.5mm}
.abstract .ab-h{column-span:all;font:700 8.4pt var(--sans);margin:0 0 4pt}
.abstract p{font-size:9.2pt;line-height:1.38;text-align:justify;margin:0 0 5pt}
.abstract strong{font:600 8.4pt var(--sans);color:var(--accent);letter-spacing:.01em}
.glance{display:flex;border-bottom:.6pt solid #181c20;margin:0 0 12pt}
.glance div{flex:1;padding:7pt 10pt 7pt 0;margin-right:10pt;border-right:.4pt solid #cfd5da}
.glance div:last-child{border-right:0;margin-right:0}
.glance b{display:block;font:600 19pt/1 var(--serif);color:var(--accent);margin-bottom:3pt}
.glance span{display:block;font:7.4pt/1.3 var(--sans);color:#3d464f}
.cols{column-count:2;column-gap:6.5mm}
h2{font:700 9.6pt var(--sans);margin:11pt 0 3pt;break-after:avoid;color:#101316}
h2 .num{color:var(--accent);margin-right:5pt}
h3{font:italic 600 9.4pt var(--serif);margin:8pt 0 2pt;break-after:avoid}
p{margin:0;text-align:justify;orphans:2;widows:2}
.cols p+p{text-indent:1.1em}
h2+p,h3+p,figure+p,.eqs+p{text-indent:0}
a{color:var(--accent);text-decoration:none}
figure{margin:9pt 0 11pt;break-inside:avoid}
figure.wide{column-span:all}
figure.tbl{break-inside:auto;column-span:none}
figure.hero{margin:12pt 0 4pt}
figure svg{width:100%;height:auto}
figure.map svg{width:78%;margin:0 11%}
figcaption{font:7.7pt/1.35 var(--sans);color:#2f373f;margin-top:5pt;text-align:left}
figcaption b{font-weight:700;color:#101316}
.tcap{margin:0 0 5pt}
table{width:100%;border-collapse:collapse;font:7.5pt/1.3 var(--sans);font-variant-numeric:tabular-nums}
thead th{text-align:left;border-top:.8pt solid #181c20;border-bottom:.5pt solid #181c20;
  padding:3pt 5pt 3pt 0;font-weight:600}
tbody td{padding:2.4pt 5pt 2.4pt 0;border-bottom:.3pt solid #e1e5e8;vertical-align:top}
tbody tr:last-child td{border-bottom:.8pt solid #181c20}
.r{text-align:right}.c{text-align:center}
.dp{color:#1d6b60}.dm{color:#c9851c}.dz{color:#8e98a3}.dn{color:#b83b35}
table.ledger{font-size:7.1pt}
table.ledger td.q{font-family:var(--serif);font-style:italic;font-size:8pt;color:#181c20;width:52%}
table.ledger td.doi{color:#59626b;font-size:6.6pt;word-break:break-all;width:17%}
.eqs{margin:7pt 0 8pt}
.eq{display:flex;align-items:center;justify-content:space-between;margin:3pt 0}
.eq svg{height:auto;max-width:88%}
.eq span{font:8pt var(--sans);color:#59626b}
h2.refs{margin-top:12pt}
div.refs p{font:7.3pt/1.32 var(--sans);text-align:left;padding-left:9pt;text-indent:-9pt;
  margin-bottom:2.6pt;color:#2f373f}
div.refs p+p{text-indent:-9pt}
"""


def _heading(line, level):
    m = re.match(r"^(#{1,6})\s+(.*\S)\s*$", line)
    return m.group(2).strip() if m and len(m.group(1)) == level else None


def split_draft(text):
    """(title, abstract_md, body_md, refs_md) from a compiled draft."""
    lines = text.splitlines()
    title = None
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i < len(lines) and _heading(lines[i], 1):
        title = _heading(lines[i], 1)
        lines = lines[i + 1:]
    abstract, body, refs, lead = [], [], [], []
    target = body
    for line in lines:
        h2 = _heading(line, 2) or _heading(line, 1)
        if h2:
            name = h2.lower().strip(" :")
            if name in ABSTRACT_NAMES and not abstract:
                target = abstract
                continue
            if name in REFERENCE_NAMES:
                target = refs
                continue
            if target is abstract:
                target = body
        if target is abstract and PLACEHOLDER.match(line.strip()):
            # A figure placed after the abstract belongs to the page, not to
            # the abstract text: it opens the body, where it becomes the hero.
            lead.append(line)
            continue
        target.append(line)
    body = lead + ([""] if lead else []) + body
    return title, "\n".join(abstract).strip(), "\n".join(body).strip(), "\n".join(refs).strip()


def _svg_inline(path):
    text = Path(path).read_text(encoding="utf-8")
    text = re.sub(r"<\?xml[^>]*\?>", "", text)
    text = re.sub(r"<!DOCTYPE[^>]*>", "", text, flags=re.S)
    text = re.sub(r"<metadata>.*?</metadata>", "", text, flags=re.S)
    return text.strip()


def _pandoc(md):
    try:
        r = subprocess.run(["pandoc", "-f", "markdown", "-t", "html5", "--wrap=none"],
                           input=md, capture_output=True, text=True, timeout=120)
    except FileNotFoundError:
        raise JournalError("pandoc is not installed; the journal template needs it")
    if r.returncode != 0:
        raise JournalError(f"pandoc failed (exit {r.returncode}): {r.stderr.strip()}")
    return r.stdout


def find_placeholders(body_md):
    """[(line_index, kind, name)]; unknown names are an error, not a skip."""
    found, bad = [], []
    for i, line in enumerate(body_md.splitlines()):
        m = PLACEHOLDER.match(line.strip())
        if not m:
            if re.match(r"^\s*\{(figure|table|equations):", line):
                bad.append(line.strip())
            continue
        if (m.group(1), m.group(2)) not in SLOTS:
            bad.append(line.strip())
            continue
        found.append((i, m.group(1), m.group(2)))
    if bad:
        known = ", ".join("{%s:%s}" % k for k in SLOTS)
        raise JournalError("unknown placeholder line(s): " + "; ".join(bad) + f". Known: {known}")
    return found


def _glance(research):
    if not research:
        return ""
    research = Path(research)
    index_path = research / "index.json"
    if not index_path.exists():
        return ""
    index = json.loads(index_path.read_text(encoding="utf-8"))
    items = [(index.get("studies"), "studies with outcome data"),
             (index.get("reports"), "outcome reports, each quoted verbatim")]
    tier3 = sum(v.get("k_tier3", 0) for v in index.get("outcomes", {}).values())
    items.append((tier3, "reports from randomized or controlled designs"))
    src = research / "sources.json"
    if src.exists():
        records = json.loads(src.read_text(encoding="utf-8"))
        items.append((sum(1 for r in records if r.get("doi")), "sources with a resolved DOI"))
    cells = "".join(f"<div><b>{n:,}</b><span>{html.escape(t)}</span></div>"
                    for n, t in items if isinstance(n, int))
    return f"<div class=glance>{cells}</div>" if cells else ""


def build_html(draft_path, figures_dir=None, research_dir=None, brand="OpenDraft",
               kind=None, byline=None, masthead_note=None, lang="en", glance=True,
               font_dir=FONT_DIR):
    """(html, warnings) for the journal page."""
    text = Path(draft_path).read_text(encoding="utf-8")
    title, abstract_md, body_md, refs_md = split_draft(text)
    warnings = []
    figures_dir = Path(figures_dir) if figures_dir else None
    captions = {}
    if figures_dir and (figures_dir / "captions.json").exists():
        captions = json.loads((figures_dir / "captions.json").read_text(encoding="utf-8"))

    placeholders = find_placeholders(body_md)
    lines = body_md.splitlines()
    first_h2 = next((i for i, l in enumerate(lines) if _heading(l, 2)), len(lines))
    hero_html = ""
    rendered = {}
    counters = {"figure": 0, "table": 0}

    def render(kind_, name, hero=False):
        fname, cap_key, role = SLOTS[(kind_, name)]
        if role == "equations":
            eqs = []
            for k, f in enumerate(EQUATION_FILES, 1):
                p = ASSETS / f
                if not p.exists():
                    raise JournalError(f"{{equations:{name}}} needs {p}, which is missing from the bundle")
                eqs.append(f"<div class=eq>{_svg_inline(p)}<span>({k})</span></div>")
            return f"<div class=eqs>{''.join(eqs)}</div>"
        if not figures_dir or not (figures_dir / fname).exists():
            raise JournalError(
                f"{{{kind_}:{name}}} is in the draft but {(figures_dir or Path('research/figures')) / fname} "
                "does not exist. Run: python3 scripts/evidence.py figures research -o research/figures")
        counters[role] += 1
        label, caption = captions.get(cap_key, ("", ""))
        head = f"<b>{'Fig.' if role == 'figure' else 'Table'} {counters[role]} | {html.escape(label)}</b> "
        cap = f"<figcaption{' class=tcap' if role == 'table' else ''}>{head}{caption}</figcaption>"
        content = (figures_dir / fname).read_text(encoding="utf-8")
        if role == "table":
            return f"</main><figure class=\"wide tbl\">{cap}{content}</figure><main class=cols>"
        cls = "hero" if hero else ("col" if name == "source-flow" else "wide")
        if name == "evidence-map":
            cls += " map"
        return f"<figure class=\"{cls}\">{_svg_inline(figures_dir / fname)}{cap}</figure>"

    for idx, kind_, name in placeholders:
        if kind_ == "figure" and name == "evidence-profile" and idx < first_h2 and not hero_html:
            hero_html = render(kind_, name, hero=True)
            lines[idx] = ""
        else:
            token = f"JOURNALSLOT{len(rendered)}"
            rendered[token] = (kind_, name)
            lines[idx] = f"\n{token}\n"
    body_md = ADJACENT_CITES.sub(r"\1; ", "\n".join(lines))
    body = _pandoc(body_md)
    for token, (kind_, name) in rendered.items():
        block = render(kind_, name)
        if f"<p>{token}</p>" not in body:
            raise JournalError(f"placeholder {{{kind_}:{name}}} did not survive pandoc as its own paragraph")
        body = body.replace(f"<p>{token}</p>", block)

    n = [0]

    def number(m):
        n[0] += 1
        return f"<h2><span class=num>{n[0]}</span>{m.group(2)}</h2>"

    body = re.sub(r"<h2( id=\"[^\"]*\")?>(.*?)</h2>", number, body)
    refs_html = ""
    if refs_md:
        refs_html = (f"<h2 class=refs><span class=num>{n[0] + 1}</span>References</h2>"
                     f"<div class=refs>{_pandoc(refs_md)}</div>")
    abstract_html = ""
    if abstract_md:
        abstract_html = f"<section class=abstract><p class=ab-h>Abstract</p>{_pandoc(abstract_md)}</section>"

    main_t, sub_t = (title or "").split(": ", 1) if title and ": " in title else (title or "", "")
    faces, missing = font_faces(font_dir)
    if missing:
        warnings.append("bundled fonts missing, falling back to system fonts: " + ", ".join(missing))
    meta = f"<span class=meta>{html.escape(masthead_note)}</span>" if masthead_note else "<span class=meta></span>"
    parts = [
        f"<!doctype html><html lang=\"{html.escape(lang)}\"><head><meta charset=utf-8>",
        f"<title>{html.escape(title or 'Draft')}</title><style>{faces}\n{CSS}</style></head><body>",
        f"<header class=mast><span class=brand>{html.escape(brand)}</span>{meta}</header>",
        f"<p class=kind>{html.escape(kind)}</p>" if kind else "<div class=spacer></div>",
        f"<h1>{html.escape(main_t)}</h1>" if main_t else "",
        f"<p class=subtitle>{html.escape(sub_t)}</p>" if sub_t else "",
        f"<p class=byline>{html.escape(byline)}</p>" if byline else "",
        abstract_html,
        _glance(research_dir) if glance else "",
        hero_html,
        f"<main class=cols>{body}{refs_html}</main></body></html>",
    ]
    return "\n".join(p for p in parts if p), warnings


def strip_placeholders(text):
    """(text, [placeholder]) for the non-journal exports, which cannot place
    the figures: the lines are removed and named, never passed through as
    literal braces in somebody's docx."""
    kept, removed = [], []
    for line in text.splitlines():
        if PLACEHOLDER.match(line.strip()):
            removed.append(line.strip())
        else:
            kept.append(line)
    return "\n".join(kept) + ("\n" if text.endswith("\n") else ""), removed


def _build_parser():
    p = argparse.ArgumentParser(prog="journal.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("draft", help="The compiled draft, final.md")
    p.add_argument("-o", "--output", required=True, help="HTML file to write")
    p.add_argument("--figures", help="Directory evidence.py figures wrote")
    p.add_argument("--research", help="research/ directory for the at-a-glance numbers")
    p.add_argument("--brand", default="OpenDraft", help="Masthead name")
    return p


def main(argv=None):
    args = _build_parser().parse_args(argv)
    try:
        page, warnings = build_html(args.draft, figures_dir=args.figures,
                                    research_dir=args.research, brand=args.brand)
    except (JournalError, OSError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    for w in warnings:
        print(f"Warning: {w}", file=sys.stderr)
    Path(args.output).write_text(page, encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
