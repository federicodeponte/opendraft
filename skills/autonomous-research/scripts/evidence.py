#!/usr/bin/env python3
"""Evidence extraction bookkeeping: abstracts, verbatim quote checks, the
evidence index, and the figures and tables drawn from them.

Standard library only. The model decides what a study found; this script
decides nothing. It fetches the text the model is allowed to quote, refuses
any quote that is not in that text, does the arithmetic, and draws the
figures, so that every mark on every figure traces to a sentence a reader can
find in the source.

    evidence.py abstracts research/sources.json -o research/abstracts.json
    evidence.py check research/evidence.json --abstracts research/abstracts.json \\
        [--texts research/texts] [-d research/citations.json]
    evidence.py index research/evidence.json -o research/index.json
    evidence.py figures research -o research/figures

Quotes come from the OpenAlex abstract. Where OpenAlex has none, or the
source has no DOI, the text the quote comes from is saved under
research/texts/ (research/texts/<id>.txt, or the DOI with every character
outside [A-Za-z0-9._-] replaced by "_", plus .txt) and quoted from there.

`research/evidence.json` is written by the model at stage 4.5. Its shape:

    {
      "outcome_order": ["productivity", "wellbeing", "retention"],
      "studies": [
        {
          "doi": "10.5271/sjweh.3610",        (or "id" for a source with no DOI)
          "label": "Schiller et al. 2016",
          "country": "Sweden",
          "design": "Cluster RCT",
          "tier": 3,                          3 randomized or controlled,
                                              2 longitudinal, panel or pilot,
                                              1 cross-sectional or qualitative
          "n": 580,                           or null when not reported
          "type": "Reduced hours",
          "trial": "Swedish social services trial",   optional grouping
          "outcomes": {"wellbeing": ["+", "<verbatim sentence>"]}
        }
      ]
    }

A bare list of studies is accepted too; outcome order then follows first
appearance. Directions are "+" improved, "~" mixed, "0" no change and "-"
worse.

The evidence index is descriptive. For each outcome o it weights every report
i by its design tier, shared across reports from the same trial,

    w_i = tier_i / m_i      (m_i = reports from the same trial for o)
    S_o = sum(w_i s_i) / sum(w_i),  s = 1, 1/2, 0, -1 for + ~ 0 -
    M_o = sum(w_i)

and recomputes S_o with each report left out in turn. It summarizes the
direction and design weight of reported findings. It is not a pooled effect
size and must never be described as one.
"""
import argparse
import html
import json
import math
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sources  # noqa: E402  (UA and DOI normalisation are shared, not copied)

DIRECTIONS = {"+": 1.0, "~": 0.5, "0": 0.0, "-": -1.0}
DIRECTION_LABEL = {"+": "Improved", "~": "Mixed", "0": "No change", "-": "Worse"}
DIRECTION_ICON = {"+": "▲", "~": "◆", "0": "●", "-": "▼"}
DIRECTION_CLASS = {"+": "dp", "~": "dm", "0": "dz", "-": "dn"}
DIRECTION_GLYPH = {"+": "+", "~": "±", "0": "0", "-": "−"}
TIERS = (1, 2, 3)

INK = "#181c20"
MUTE = "#5d6771"
GRID = "#e3e6ea"
COLOR = {"+": "#1d6b60", "~": "#d08a1e", "0": "#9aa3ad", "-": "#b83b35"}
TIER_OPACITY = {3: 1.0, 2: 0.72, 1: 0.45}
SANS = "'Source Sans 3', 'Source Sans Pro', 'Helvetica Neue', Arial, sans-serif"
SERIF = "'STIX Two Text', STIXGeneral, 'Times New Roman', serif"

OPENALEX = "https://api.openalex.org/works/doi:{doi}?select=id,doi,title,publication_year,abstract_inverted_index"
FETCH_ATTEMPTS = 4


class EvidenceError(Exception):
    """A failure the caller must see; main() turns it into exit 1."""


# --- abstracts ---------------------------------------------------------------

def rebuild_abstract(inverted):
    """OpenAlex stores abstracts as {word: [positions]}; put them back in order."""
    if not inverted:
        return ""
    slots = {}
    for word, positions in inverted.items():
        for p in positions:
            slots[p] = word
    return " ".join(slots[i] for i in sorted(slots))


def _fetch_openalex(doi, get=None, sleep=time.sleep):
    get = get or sources._get
    url = OPENALEX.format(doi=urllib.parse.quote(doi, safe="/"))
    if sources._CONTACT:
        url += "&mailto=" + urllib.parse.quote(sources._CONTACT)
    delay = 1.0
    for attempt in range(FETCH_ATTEMPTS):
        try:
            return get(url)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code not in (429, 500, 502, 503, 504) or attempt == FETCH_ATTEMPTS - 1:
                raise
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt == FETCH_ATTEMPTS - 1:
                raise
        sleep(delay)
        delay *= 2
    return None


def fetch_abstracts(records, existing=None, get=None, sleep=time.sleep, pause=0.12):
    """{doi: {"abstract", "title", "year", "source"}} for every record with a DOI.

    Entries already in `existing` are kept as they are, so a rerun after a
    rate limit only asks for what is still missing. A DOI OpenAlex does not
    know, or knows without an abstract, is stored with an empty abstract: it
    stays citable for its existence, never quotable for a finding."""
    out = dict(existing or {})
    failed = []
    for rec in records:
        doi = sources._norm_doi(rec.get("doi"))
        if not doi or doi in out:
            continue
        try:
            work = _fetch_openalex(doi, get=get, sleep=sleep)
        except Exception as e:  # noqa: BLE001  (reported, never swallowed)
            failed.append(f"{doi}: {e}")
            continue
        text = rebuild_abstract((work or {}).get("abstract_inverted_index"))
        out[doi] = {"abstract": text,
                    "title": (work or {}).get("title") or rec.get("title") or "",
                    "year": (work or {}).get("publication_year") or rec.get("year"),
                    "source": "openalex" if work else "none"}
        sleep(pause)
    return out, failed


def abstract_text(entry):
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        return entry.get("abstract") or ""
    return ""


# --- evidence file -----------------------------------------------------------

def load_evidence(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, list):
        studies, order = data, None
    elif isinstance(data, dict) and isinstance(data.get("studies"), list):
        studies, order = data["studies"], data.get("outcome_order")
    else:
        raise EvidenceError(f"{path}: expected a list of studies or "
                            '{"studies": [...]}')
    return studies, outcome_names(studies, order)


def outcome_names(studies, order=None):
    seen = []
    for s in studies:
        for o in (s.get("outcomes") or {}):
            if o not in seen:
                seen.append(o)
    if order:
        missing = [o for o in seen if o not in order]
        return [o for o in order if o in seen] + missing
    return seen


def study_key(s):
    doi = sources._norm_doi(s.get("doi"))
    return doi or (s.get("id") or "").strip()


_QUOTES = {"\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
           "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u00ab": '"', "\u00bb": '"'}
_DASHES = "\u2010\u2011\u2012\u2013\u2014\u2015\u2212"


def normalise(text):
    """What 'verbatim' is allowed to ignore: Unicode form, quote style, dash
    style, soft hyphens and runs of whitespace. Nothing else, not case, not
    punctuation, not word order."""
    t = unicodedata.normalize("NFKC", text or "")
    t = t.replace("­", "")
    for k, v in _QUOTES.items():
        t = t.replace(k, v)
    for d in _DASHES:
        t = t.replace(d, "-")
    return re.sub(r"\s+", " ", t).strip()


def schema_problems(studies):
    problems = []
    seen = set()
    for i, s in enumerate(studies):
        where = f"study {i + 1} ({s.get('label') or 'no label'})"
        if not isinstance(s, dict):
            problems.append(f"{where}: not an object")
            continue
        key = study_key(s)
        if not key:
            problems.append(f"{where}: needs a doi, or an id for a source with no DOI")
        elif key in seen:
            problems.append(f"{where}: {key} appears twice; one entry per study")
        seen.add(key)
        for field in ("label", "country", "design", "type"):
            if not isinstance(s.get(field), str) or not s.get(field).strip():
                problems.append(f"{where}: missing {field}")
        if s.get("tier") not in TIERS:
            problems.append(f"{where}: tier must be 1, 2 or 3, got {s.get('tier')!r}")
        n = s.get("n")
        if n is not None and (not isinstance(n, int) or isinstance(n, bool) or n <= 0):
            problems.append(f"{where}: n must be a positive integer or null, got {n!r}")
        if "trial" in s and (not isinstance(s["trial"], str) or not s["trial"].strip()):
            problems.append(f"{where}: trial, when present, must be a non-empty string")
        outs = s.get("outcomes")
        if not isinstance(outs, dict) or not outs:
            problems.append(f"{where}: outcomes must map at least one outcome to [direction, quote]")
            continue
        for o, cell in outs.items():
            if (not isinstance(cell, list) or len(cell) != 2
                    or cell[0] not in DIRECTIONS or not isinstance(cell[1], str)
                    or not cell[1].strip()):
                problems.append(f"{where}: outcome {o!r} must be [one of + ~ 0 -, a quote]")
    return problems


def text_name(doi):
    """File name under research/texts/ for a DOI whose abstract OpenAlex lacks."""
    return re.sub(r"[^A-Za-z0-9._-]", "_", doi) + ".txt"


def quote_problems(studies, abstracts, texts_dir=None):
    """[str] for every quote that is not a verbatim substring of its source."""
    problems = []
    for s in studies:
        if not isinstance(s, dict) or not isinstance(s.get("outcomes"), dict):
            continue
        doi = sources._norm_doi(s.get("doi"))
        label = s.get("label") or study_key(s)
        if doi:
            source_text = abstract_text(abstracts.get(doi))
            origin = f"the OpenAlex abstract of {doi}"
            saved = Path(texts_dir) / text_name(doi) if texts_dir else None
            if not source_text and saved and saved.exists():
                source_text, origin = saved.read_text(encoding="utf-8"), str(saved)
            if not source_text:
                problems.append(f"{label}: {doi} has no retrieved abstract and no saved text "
                                f"research/texts/{text_name(doi)}, so nothing from it can be "
                                "quoted as a finding")
                continue
        else:
            ident = (s.get("id") or "").strip()
            path = Path(texts_dir) / f"{ident}.txt" if texts_dir else None
            if not path or not path.exists():
                problems.append(f"{label}: no DOI, and no text file "
                                f"{path or 'research/texts/' + ident + '.txt'} to quote from")
                continue
            source_text = path.read_text(encoding="utf-8")
            origin = str(path)
        haystack = normalise(source_text)
        for o, cell in s["outcomes"].items():
            if not (isinstance(cell, list) and len(cell) == 2):
                continue
            quote = normalise(cell[1])
            if quote.strip("\"'") not in haystack:
                problems.append(f"{label} / {o}: quote not found verbatim in {origin}: "
                                f"\"{cell[1][:90]}\"")
    return problems


def citation_problems(studies, citations_path):
    db = json.loads(Path(citations_path).read_text(encoding="utf-8"))
    entries = db if isinstance(db, list) else db.get("citations", db)
    known = set()
    if isinstance(entries, dict):
        entries = list(entries.values())
    for e in entries:
        if isinstance(e, dict) and e.get("doi"):
            known.add(sources._norm_doi(e["doi"]))
    return [f"{s.get('label')}: {sources._norm_doi(s['doi'])} is not in {citations_path}"
            for s in studies
            if isinstance(s, dict) and s.get("doi")
            and sources._norm_doi(s["doi"]) not in known]


# --- index -------------------------------------------------------------------

def compute_index(studies, order):
    """{"outcomes": {o: {...}}, "method": ...}; every number the paper reports."""
    counts = {}
    for s in studies:
        for o in s["outcomes"]:
            key = (s.get("trial") or study_key(s), o)
            counts[key] = counts.get(key, 0) + 1

    def score(items):
        total = sum(it["w"] for it in items)
        return sum(it["w"] * DIRECTIONS[it["direction"]] for it in items) / total if total else 0.0

    out = {}
    for o in order:
        items = []
        for s in studies:
            if o not in s["outcomes"]:
                continue
            m = counts[(s.get("trial") or study_key(s), o)]
            items.append({"label": s["label"], "key": study_key(s),
                          "direction": s["outcomes"][o][0], "tier": s["tier"],
                          "m": m, "w": round(s["tier"] / m, 6)})
        loo = [score(items[:i] + items[i + 1:]) for i in range(len(items))] if len(items) > 1 else []
        S = score(items)
        out[o] = {"k": len(items),
                  "M": round(sum(it["w"] for it in items), 4),
                  "S": round(S, 4),
                  "loo_min": round(min(loo), 4) if loo else None,
                  "loo_max": round(max(loo), 4) if loo else None,
                  "k_tier3": sum(1 for it in items if it["tier"] == 3),
                  "items": items}
    return {"method": "w_i = tier_i / m_i; S_o = sum(w_i s_i) / sum(w_i); "
                      "M_o = sum(w_i); s = 1, 0.5, 0, -1 for + ~ 0 -. "
                      "Descriptive, not a pooled effect size.",
            "studies": len(studies),
            "reports": sum(v["k"] for v in out.values()),
            "outcome_order": list(order),
            "outcomes": out}


# --- SVG helpers -------------------------------------------------------------

def _t(x, y, s, size=11, anchor="start", weight=400, color=INK, family=SANS, italic=False, extra=""):
    style = f"font-family:{family};font-size:{size}px;font-weight:{weight}"
    if italic:
        style += ";font-style:italic"
    return (f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" fill="{color}" '
            f'style="{style}"{extra}>{html.escape(str(s))}</text>')


def _svg(width, height, body, label):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
            f'width="{width}" height="{height}" role="img" aria-label="{html.escape(label)}">'
            + "".join(body) + "</svg>\n")


def _nice_step(maximum):
    for step in (1, 2, 5, 10, 20, 25, 50, 100):
        if maximum / step <= 6:
            return step
    return 200


def _fmt(x):
    return f"{x:.2f}"


def profile_panel(index, x0, y0, width):
    """Panel a: one bar per outcome, one segment per report, length = weight."""
    order = index["outcome_order"]
    outs = index["outcomes"]
    maxM = max((outs[o]["M"] for o in order), default=1) or 1
    label_w, value_w = 92, 92
    bar_w = width - label_w - value_w
    scale = bar_w / maxM
    row = 46
    body = [_t(x0, y0 + 10, "a", 15, weight=700)]
    top = y0 + 30
    for r, o in enumerate(order):
        v = outs[o]
        y = top + r * row
        x = x0 + label_w
        items = sorted(v["items"], key=lambda it: (-it["tier"], -DIRECTIONS[it["direction"]], it["label"]))
        for it in items:
            w = it["w"] * scale
            body.append(f'<rect x="{x:.2f}" y="{y:.1f}" width="{w:.2f}" height="24" '
                        f'fill="{COLOR[it["direction"]]}" fill-opacity="{TIER_OPACITY[it["tier"]]}" '
                        f'stroke="#ffffff" stroke-width="1.4"><title>{html.escape(it["label"])}</title></rect>')
            x += w
        body.append(_t(x0 + label_w - 8, y + 12, o.capitalize(), 11.5, "end", 600))
        body.append(_t(x0 + label_w - 8, y + 25, f"{v['k']} report" + ("s" if v["k"] != 1 else ""),
                       9, "end", color=MUTE))
        body.append(f'<text x="{x + 8:.1f}" y="{y + 11:.1f}" fill="{INK}" style="font-family:{SANS};font-size:11.5px">'
                    f'<tspan style="font-family:{SERIF};font-style:italic">S</tspan> = {_fmt(v["S"])}</text>')
        loo = (f"LOO {_fmt(v['loo_min'])}\u2013{_fmt(v['loo_max'])}" if v["loo_min"] is not None
               and v["loo_min"] != v["loo_max"] else
               (f"LOO {_fmt(v['loo_min'])}" if v["loo_min"] is not None else "single report"))
        body.append(_t(x + 8, y + 24, loo, 9, color=MUTE))
    axis_y = top + len(order) * row - 6
    body.append(f'<line x1="{x0 + label_w}" y1="{axis_y}" x2="{x0 + label_w + bar_w}" y2="{axis_y}" '
                f'stroke="{INK}" stroke-width="0.8"/>')
    step = _nice_step(maxM)
    tick = 0
    while tick <= maxM + 1e-9:
        tx = x0 + label_w + tick * scale
        body.append(f'<line x1="{tx:.1f}" y1="{axis_y}" x2="{tx:.1f}" y2="{axis_y + 4}" stroke="{INK}" stroke-width="0.8"/>')
        body.append(_t(tx, axis_y + 15, tick, 9, "middle", color=MUTE))
        tick += step
    body.append(f'<text x="{x0 + label_w + bar_w / 2:.1f}" y="{axis_y + 30}" text-anchor="middle" fill="{INK}" '
                f'style="font-family:{SANS};font-size:10px">Design-weighted evidence mass '
                f'<tspan style="font-family:{SERIF};font-style:italic">M</tspan></text>')
    ly = axis_y + 50
    lx = x0 + label_w
    for d in ("+", "~", "0", "-"):
        if not any(it["direction"] == d for o in order for it in outs[o]["items"]):
            continue
        body.append(f'<rect x="{lx}" y="{ly - 8}" width="10" height="10" fill="{COLOR[d]}"/>')
        body.append(_t(lx + 14, ly + 1, DIRECTION_LABEL[d], 9, color=MUTE))
        lx += 26 + len(DIRECTION_LABEL[d]) * 5
    body.append(_t(lx + 6, ly + 1, "Shade: design tier 3 · 2 · 1", 9, color=MUTE))
    for k, t in enumerate((3, 2, 1)):
        body.append(f'<rect x="{lx + 136 + k * 13}" y="{ly - 8}" width="10" height="10" '
                    f'fill="{COLOR["+"]}" fill-opacity="{TIER_OPACITY[t]}"/>')
    return body, ly + 10


def timeline_panel(records, abstracts, study_dois, x0, y0, width, height):
    """Panel b: every source as one dot at its publication year."""
    years = [r.get("year") for r in records if isinstance(r.get("year"), int)]
    body = [_t(x0 - 14, y0 + 10, "b", 15, weight=700)]
    if not years:
        body.append(_t(x0, y0 + 40, "No publication years recorded", 10, color=MUTE))
        return body
    lo = (min(years) // 5) * 5 - 2
    hi = max(years) + 3
    axis_y = y0 + height - 40
    scale = width / (hi - lo)
    stacks = {}
    kinds = []
    for r in records:
        y = r.get("year")
        if not isinstance(y, int):
            continue
        doi = sources._norm_doi(r.get("doi"))
        kind = 0 if doi in study_dois else (1 if abstract_text(abstracts.get(doi)) else 2)
        stacks.setdefault(y, []).append(kind)
        kinds.append(kind)
    fills = {0: "#1d6b60", 1: "#8fbdb4", 2: "#d3d8dc"}
    tallest = max(len(v) for v in stacks.values())
    dy = min(9.0, (axis_y - y0 - 70) / max(tallest, 1))
    for y in sorted(stacks):
        cx = x0 + (y - lo) * scale
        for k, kind in enumerate(sorted(stacks[y])):
            body.append(f'<circle cx="{cx:.2f}" cy="{axis_y - 6 - k * dy:.2f}" r="{min(3.4, dy / 2 - 0.2):.2f}" '
                        f'fill="{fills[kind]}" stroke="#ffffff" stroke-width="0.5"/>')
    body.append(f'<line x1="{x0}" y1="{axis_y}" x2="{x0 + width}" y2="{axis_y}" stroke="{INK}" stroke-width="0.8"/>')
    span = hi - lo
    step = 5 if span <= 30 else 10 if span <= 60 else 20 if span <= 120 else 50
    t = ((lo + step - 1) // step) * step
    while t <= hi:
        tx = x0 + (t - lo) * scale
        body.append(f'<line x1="{tx:.1f}" y1="{axis_y}" x2="{tx:.1f}" y2="{axis_y + 4}" stroke="{INK}" stroke-width="0.8"/>')
        body.append(_t(tx, axis_y + 15, t, 9, "middle", color=MUTE))
        t += step
    body.append(_t(x0 + width / 2, axis_y + 30, f"Publication year, {len(kinds)} sources", 10, "middle"))
    legend = [(0, "Outcome study"), (1, "Abstract retrieved"), (2, "Metadata only")]
    for k, (kind, text) in enumerate(legend):
        ly = y0 + 30 + k * 14
        body.append(f'<circle cx="{x0 + 5}" cy="{ly - 3}" r="3.4" fill="{fills[kind]}"/>')
        body.append(_t(x0 + 13, ly + 1, f"{text} ({kinds.count(kind)})", 9, color=MUTE))
    return body


def figure_profile(index, records, abstracts, study_dois):
    width = 720
    body, bottom = profile_panel(index, 0, 0, 450)
    height = max(bottom + 6, 200)
    body += timeline_panel(records, abstracts, study_dois, 505, 0, 205, height - 42)
    return _svg(width, height, body, "Evidence profile per outcome and publication years of the sources")


def figure_map(studies, order):
    rows = sorted(studies, key=lambda s: (-s["tier"], -(s.get("n") or 0), s["label"]))
    col_w, label_w, row_h, top = 82, 170, 21, 34
    width = label_w + col_w * len(order) + 20
    height = top + row_h * len(rows) + 58
    body = []
    for j, o in enumerate(order):
        body.append(_t(label_w + col_w * j + col_w / 2, 16, o.capitalize(), 10.5, "middle", 600))
    for i, s in enumerate(rows):
        y = top + i * row_h + row_h / 2
        body.append(f'<line x1="{label_w - 4}" y1="{y:.1f}" x2="{width - 10}" y2="{y:.1f}" stroke="{GRID}" stroke-width="0.7"/>')
        body.append(_t(label_w - 12, y + 3.5, s["label"], 10, "end"))
        for j, o in enumerate(order):
            if o not in s["outcomes"]:
                continue
            d = s["outcomes"][o][0]
            r = 6.2 + (1.9 * math.log10(s["n"]) if s.get("n") else 1.6)
            cx = label_w + col_w * j + col_w / 2
            body.append(f'<circle cx="{cx:.1f}" cy="{y:.1f}" r="{r:.2f}" fill="{COLOR[d]}" stroke="#ffffff" stroke-width="1"/>')
            body.append(_t(cx, y + 3.4, DIRECTION_GLYPH[d], 9.5, "middle", 700, "#ffffff"))
    ly = top + row_h * len(rows) + 22
    lx = label_w
    for d in ("+", "~", "0", "-"):
        if not any(s["outcomes"].get(o, [None])[0] == d for s in studies for o in order):
            continue
        body.append(f'<circle cx="{lx + 5}" cy="{ly - 3}" r="5" fill="{COLOR[d]}"/>')
        body.append(_t(lx + 14, ly + 1, DIRECTION_LABEL[d], 9.5, color=MUTE))
        lx += 34 + len(DIRECTION_LABEL[d]) * 5.2
    body.append(_t(label_w, ly + 20, "Ordered by design tier, then sample size. Marker size scales with n.",
                   9, color=MUTE))
    return _svg(width, height, body, "Evidence map of reported effects by study and outcome")


def figure_flow(records, abstracts, studies):
    with_doi = [sources._norm_doi(r.get("doi")) for r in records if sources._norm_doi(r.get("doi"))]
    n_abs = sum(1 for d in with_doi if abstract_text(abstracts.get(d)))
    n_meta = len(with_doi) - n_abs
    n_study = sum(1 for s in studies if sources._norm_doi(s.get("doi")))
    n_grey = sum(1 for s in studies if not sources._norm_doi(s.get("doi")))
    body = []

    def box(x, y, w, h, lines, fill="#eef4f2", stroke="#1d6b60"):
        body.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="7" fill="{fill}" stroke="{stroke}" stroke-width="1"/>')
        for k, line in enumerate(lines):
            body.append(_t(x + w / 2, y + h / 2 + 4 + (k - (len(lines) - 1) / 2) * 13, line, 10.5, "middle"))

    def arrow(x1, y1, x2, y2):
        body.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{MUTE}" stroke-width="1"/>')
        ang = math.atan2(y2 - y1, x2 - x1)
        p1 = (x2 - 6 * math.cos(ang - 0.45), y2 - 6 * math.sin(ang - 0.45))
        p2 = (x2 - 6 * math.cos(ang + 0.45), y2 - 6 * math.sin(ang + 0.45))
        body.append(f'<polygon points="{x2},{y2} {p1[0]:.1f},{p1[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}" fill="{MUTE}"/>')

    box(60, 6, 220, 42, ["Crossref + OpenAlex queries", f"{len(with_doi)} DOI records resolved"])
    box(6, 86, 150, 42, [f"{n_abs} abstracts", "retrieved"])
    box(184, 86, 150, 42, [f"{n_meta} metadata only", "(scope map)"], "#f4f5f6", "#9aa3ad")
    box(6, 166, 150, 42, [f"{n_study} studies with", "outcome data"])
    arrow(140, 48, 88, 84)
    arrow(200, 48, 252, 84)
    arrow(81, 128, 81, 164)
    if n_grey:
        body.append(_t(176, 182, f"+ {n_grey} report" + ("s" if n_grey != 1 else "") + " without a DOI,", 9.5, color=MUTE))
        body.append(_t(176, 196, "quoted from saved full text", 9.5, color=MUTE))
    return _svg(340, 214, body, "How the retrieved records were used")


# --- tables and captions -----------------------------------------------------

def table_studies(studies, order):
    rows = sorted(studies, key=lambda s: (-s["tier"], -(s.get("n") or 0), s["label"]))
    head = "".join(f"<th class=c>{html.escape(o.capitalize()[:6])}.</th>" if len(o) > 7
                   else f"<th class=c>{html.escape(o.capitalize())}</th>" for o in order)
    body = []
    for s in rows:
        n = format(s["n"], ",") if s.get("n") else "\u2013"
        cells = "".join(
            f'<td class="c {DIRECTION_CLASS[s["outcomes"][o][0]]}">{DIRECTION_ICON[s["outcomes"][o][0]]}</td>'
            if o in s["outcomes"] else "<td class=c></td>" for o in order)
        body.append(f"<tr><td>{html.escape(s['label'])}</td><td>{html.escape(s['country'])}</td>"
                    f"<td>{html.escape(s['design'])}</td><td class=r>{n}</td>"
                    f"<td>{html.escape(s['type'])}</td>{cells}</tr>")
    return ("<table class=studies><thead><tr><th>Study</th><th>Setting</th><th>Design</th>"
            f"<th class=r>N</th><th>Type</th>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>\n")


def table_ledger(studies, order):
    rows = sorted(studies, key=lambda s: (-s["tier"], -(s.get("n") or 0), s["label"]))
    body = []
    for s in rows:
        doi = sources._norm_doi(s.get("doi"))
        src = f"doi.org/{doi}" if doi else f"{s.get('id')} (saved text)"
        for o in order:
            if o not in s["outcomes"]:
                continue
            d, q = s["outcomes"][o]
            body.append(f"<tr><td>{html.escape(s['label'])}</td><td>{html.escape(o.capitalize())}</td>"
                        f'<td class="{DIRECTION_CLASS[d]}">{DIRECTION_ICON[d]} {DIRECTION_LABEL[d]}</td>'
                        f"<td class=q>“{html.escape(q.strip())}”</td><td class=doi>{html.escape(src)}</td></tr>")
    return ("<table class=ledger><thead><tr><th>Study</th><th>Outcome</th><th>Direction</th>"
            "<th>Verbatim evidence</th><th>Source</th></tr></thead><tbody>"
            + "".join(body) + "</tbody></table>\n")


def captions(index, studies, records):
    k = len(studies)
    reports = index["reports"]
    return {
        "evidence-profile": ("Evidence at a glance.",
                             "<b>a</b>, Evidence profile per outcome. Each segment is one outcome report; its length is the "
                             "design weight <i>w</i> (equation 1), its color the reported direction and its shade the design "
                             "tier. <i>S</i>, evidence index (equation 2); LOO, leave-one-out range (equation 3). "
                             f"<b>b</b>, Publication year of the {len(records)} sources; each dot is one source."),
        "evidence-map": ("Evidence map.",
                         f"Direction of reported effects for the {k} studies with outcome data. Each marker is backed by "
                         "a verbatim sentence from the study, listed in the evidence ledger."),
        "source-flow": ("Source flow.", "How the retrieved records were used."),
        "studies": ("Characteristics of studies with outcome data.",
                    "▲ improved, ◆ mixed, ● no change, ▼ worse."),
        "ledger": ("Evidence ledger.",
                   f"Every directional marker in the evidence figures with the sentence that supports it, quoted "
                   f"verbatim from the study abstract or saved report ({reports} reports)."),
    }


def build_figures(research, out_dir):
    research = Path(research)
    out = Path(out_dir)
    studies, order = load_evidence(research / "evidence.json")
    problems = schema_problems(studies)
    if problems:
        raise EvidenceError("evidence.json fails its schema, run check first:\n  " + "\n  ".join(problems))
    index_path = research / "index.json"
    index = (json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists()
             else compute_index(studies, order))
    if index.get("outcome_order") != order or index.get("studies") != len(studies):
        raise EvidenceError(f"{index_path} is stale against evidence.json; rerun `evidence.py index`")
    records = json.loads((research / "sources.json").read_text(encoding="utf-8"))
    abs_path = research / "abstracts.json"
    abstracts = json.loads(abs_path.read_text(encoding="utf-8")) if abs_path.exists() else {}
    study_dois = {sources._norm_doi(s.get("doi")) for s in studies if s.get("doi")}
    out.mkdir(parents=True, exist_ok=True)
    files = {
        "evidence-profile.svg": figure_profile(index, records, abstracts, study_dois),
        "evidence-map.svg": figure_map(studies, order),
        "source-flow.svg": figure_flow(records, abstracts, studies),
        "table-studies.html": table_studies(studies, order),
        "table-ledger.html": table_ledger(studies, order),
        "captions.json": json.dumps(captions(index, studies, records), indent=1, ensure_ascii=False) + "\n",
    }
    for name, text in files.items():
        (out / name).write_text(text, encoding="utf-8")
    return sorted(files)


# --- CLI ---------------------------------------------------------------------

def _build_parser():
    p = argparse.ArgumentParser(prog="evidence.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("abstracts", help="Fetch OpenAlex abstracts for every DOI in sources.json")
    a.add_argument("sources")
    a.add_argument("-o", "--output", required=True)
    c = sub.add_parser("check", help="Validate evidence.json and every quote against its source text")
    c.add_argument("evidence")
    c.add_argument("--abstracts", required=True)
    c.add_argument("--texts", help="Directory of <id>.txt full texts for sources with no DOI")
    c.add_argument("-d", "--database", help="research/citations.json; every study DOI must be in it")
    i = sub.add_parser("index", help="Compute the descriptive evidence index")
    i.add_argument("evidence")
    i.add_argument("-o", "--output", required=True)
    f = sub.add_parser("figures", help="Draw the evidence figures and tables as SVG and HTML")
    f.add_argument("research", help="The research/ directory")
    f.add_argument("-o", "--output", required=True)
    return p


def main(argv=None):
    args = _build_parser().parse_args(argv)
    try:
        if args.cmd == "abstracts":
            records = json.loads(Path(args.sources).read_text(encoding="utf-8"))
            if not isinstance(records, list):
                raise EvidenceError(f"{args.sources}: expected the JSON array stage 1 wrote")
            out = Path(args.output)
            existing = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
            result, failed = fetch_abstracts(records, existing)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
            n_abs = sum(1 for v in result.values() if abstract_text(v))
            print(f"{len(result)} DOIs, {n_abs} with an abstract, {len(result) - n_abs} without -> {out}")
            if failed:
                print("Could not reach OpenAlex for these; rerun the same command to retry them:", file=sys.stderr)
                for f in failed:
                    print(f"  {f}", file=sys.stderr)
                return 1
            return 0
        if args.cmd == "check":
            studies, order = load_evidence(args.evidence)
            abstracts = json.loads(Path(args.abstracts).read_text(encoding="utf-8"))
            problems = schema_problems(studies)
            if not problems:
                problems = quote_problems(studies, abstracts, args.texts)
                if args.database:
                    problems += citation_problems(studies, args.database)
            if problems:
                print(f"{len(problems)} problem(s) in {args.evidence}:", file=sys.stderr)
                for pr in problems:
                    print(f"  {pr}", file=sys.stderr)
                return 1
            quotes = sum(len(s["outcomes"]) for s in studies)
            print(f"OK: {len(studies)} studies, {quotes} quotes, every quote found verbatim; outcomes: {', '.join(order)}")
            return 0
        if args.cmd == "index":
            studies, order = load_evidence(args.evidence)
            problems = schema_problems(studies)
            if problems:
                raise EvidenceError("evidence.json fails its schema, run check first:\n  " + "\n  ".join(problems))
            index = compute_index(studies, order)
            Path(args.output).write_text(json.dumps(index, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
            for o in order:
                v = index["outcomes"][o]
                loo = (f"{_fmt(v['loo_min'])} to {_fmt(v['loo_max'])}" if v["loo_min"] is not None else "n/a")
                print(f"{o}: S = {_fmt(v['S'])}, M = {v['M']:g}, k = {v['k']}, tier 3 = {v['k_tier3']}, leave-one-out {loo}")
            return 0
        if args.cmd == "figures":
            files = build_figures(args.research, args.output)
            print(f"Wrote {len(files)} files to {args.output}: {', '.join(files)}")
            return 0
    except (EvidenceError, OSError, json.JSONDecodeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
