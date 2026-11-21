"""Step 2 (Process): extract tables from the ICAA/Rentrak PDFs into tidy CSVs.

Outputs (data/interim/):
  weekly_top25.csv        one row per film per weekend (Top 25, all films in Spain)
  weekly_spanish.csv      one row per Spanish film per weekend (Spanish films on release)
  annual_spanish.csv      one row per Spanish film per calendar year
  extract_log.csv         per-file status (rows parsed, weekend dates, errors)

Column headers differ slightly between years, so columns are mapped by header keywords.
"""
import csv
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "icaa"
OUT = ROOT / "data" / "interim"

MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
    "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}

# header keyword -> canonical column. Order matters: first match wins per header cell.
WEEKLY_MAP = [
    ("rank", "rank"),
    ("original", "original_title"),
    ("título", "title"), ("titulo", "title"),
    ("distribu", "distributor"),
    ("sem", "weeks_on_release"),
    ("cines", "cinemas"),
    ("pantallas", "screens"),
    ("recaudación\n(acum", "gross_cum_eur"), ("recaudacion\n(acum", "gross_cum_eur"),
    ("espectadores\n(acum", "admissions_cum"),
    ("acumulad", None),  # resolved by position below
    ("recaud", "gross_eur"),
    ("espectadores", "admissions"),
    ("estreno", "release_date"),
    ("+/-", "pct_change"),
]


def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip())


def map_headers(header):
    cols, pct_seen = [], 0
    for h in header:
        hl = (h or "").lower().strip()
        name = None
        if "acum" in hl:
            name = "gross_cum_eur" if "recaud" in hl else "admissions_cum" if "espect" in hl else None
        if name is None:
            for key, canon in WEEKLY_MAP:
                if key in hl and canon:
                    name = canon
                    break
        if name == "pct_change":
            pct_seen += 1
            name = "gross_pct_change" if pct_seen == 1 else "admissions_pct_change"
        cols.append(name)
    return cols


def to_number(s):
    s = norm(s).replace("€", "").replace("%", "").replace(".", "").replace(" ", "")
    s = s.replace(",", ".")
    if s in ("", "-", "--"):
        return ""
    try:
        v = float(s)
        return int(v) if v.is_integer() else v
    except ValueError:
        return ""


# Source filenames with a wrong date, verified against films' weeks-on-release in adjacent weekends.
DATE_OVERRIDES = {
    # Sentimental is week 5 here; it is week 3 on 13 Nov and week 6 on 4 Dec 2020 -> 27-29 Nov 2020
    "top25-27-29-diciembre.pdf": date(2020, 11, 27),
    "topespaniol-27-29-diciembre.pdf": date(2020, 11, 27),
    # La casa del caracol is week 2 here and week 1 on 11-13 Jun 2021 -> 18-20 Jun 2021
    "topespanol-18-20-mayo.pdf": date(2021, 6, 18),
}


def weekend_from_name(fname):
    """'top-25-30-enero-1-febrero-2026' -> Friday date of that weekend."""
    if fname.split("_", 1)[-1] in DATE_OVERRIDES:
        return DATE_OVERRIDES[fname.split("_", 1)[-1]]
    stem = fname.lower().replace(".pdf", "")
    years = re.findall(r"(20\d\d)", stem)
    # drop the prefix (incl. the "25" of "top-25") and the year, keep days/months
    body = re.sub(r"^.*?(top-?25|topespanol|espanol-en-cartelera)-?", "", stem.split("_", 1)[-1])
    body = re.sub(r"20\d\d", "", body)
    parts = re.findall(r"\d{1,2}|" + "|".join(MONTHS), body)
    days = [int(p) for p in parts if p.isdigit()]
    months = [MONTHS[p] for p in parts if not p.isdigit()]
    if not months and "npviembre" in body:  # typo in one source filename
        months = [11]
    if not days or not months:
        return None
    start_day, start_month = days[0], months[0]
    if len(days) >= 2 and len(months) == 1 and days[0] > days[1]:
        start_month = 12 if months[0] == 1 else months[0] - 1  # "30-1-agosto" = 30 Jul - 1 Aug
    if not years:
        if len(days) == 1:
            # single-date labels: the Friday, Saturday or Sunday of the weekend
            # (e.g. "25enero" = Sat 25 Jan 2020, Dolittle's opening weekend)
            for cy in range(2020, 2024):
                try:
                    d = date(cy, start_month, start_day)
                except ValueError:
                    continue
                if d.weekday() in (4, 5, 6):
                    cands = [d - timedelta(days=d.weekday() - 4)]
                    break
            else:
                cands = []
            if cands:
                return cands[0]
        # 2020-2021 files carry no year: the weekend starts on a Friday, and within
        # 2020-2023 a given day/month falls on Friday in exactly one year.
        hits = []
        for cy in range(2020, 2024):
            try:
                if date(cy, start_month, start_day).weekday() == 4:
                    hits.append(cy)
            except ValueError:
                pass
        if len(hits) == 1:
            return date(hits[0], start_month, start_day)
        # single-date labels that are a Sunday (e.g. "1marzo" = 28 Feb-1 Mar 2020)
        for cy in range(2020, 2024):
            try:
                d = date(cy, start_month, start_day)
            except ValueError:
                continue
            if d.weekday() == 6:
                return d - timedelta(days=2)
        return None
    y = int(years[-1])
    for cand_year in (y, y - 1, y + 1) if y else ():
        try:
            d = date(cand_year, start_month, start_day)
        except ValueError:
            continue
        if d.weekday() == 4:  # Friday
            return d
    # some weekends are reported Thu-Sun (holidays): accept nearest Friday
    try:
        d = date(y, start_month, start_day)
        return d + timedelta(days=(4 - d.weekday()) % 7) if d.weekday() < 4 else d - timedelta(days=d.weekday() - 4)
    except ValueError:
        return None


def words_to_rows(words, edges, y_tol=2.5):
    """Group words into text lines (by 'top') and columns (by x-centre within edges)."""
    lines = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if lines and abs(lines[-1][0] - w["top"]) <= y_tol:
            lines[-1][1].append(w)
        else:
            lines.append([w["top"], [w]])
    ncols = len(edges) - 1
    out = []
    for _, ws in lines:
        cells = [""] * ncols
        for w in sorted(ws, key=lambda w: w["x0"]):
            x = w["x0"] + 1  # left edge decides the column (text is left/right aligned in cells)
            for i in range(ncols):
                if edges[i] - 1 <= x < edges[i + 1]:
                    cells[i] = (cells[i] + " " + w["text"]).strip()
                    break
        out.append(cells)
    return out


def extract_pdf(path):
    """Only the header row is ruled in these PDFs; data rows are free text.
    So: read the header table to get column x-boundaries, then re-extract the
    area below it using those boundaries as explicit vertical lines and text
    alignment for rows."""
    rows, header_cols, edges = [], None, None
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            top = 0
            bottom = page.height
            for t in page.find_tables():
                data = t.extract()
                if not data or not data[0]:
                    continue
                first = norm(data[0][0]).lower()
                if first.startswith("rank"):
                    header_cols = map_headers([c or "" for c in data[0]])
                    xs = sorted({round(c[0], 1) for c in t.rows[0].cells if c} |
                                {round(c[2], 1) for c in t.rows[0].cells if c})
                    edges = xs
                    top = t.rows[0].bbox[3]  # bottom of the header row (some PDFs rule every row)
                elif any("TOTAL" in (c or "") for c in data[0]) and t.bbox[1] > top:
                    bottom = min(bottom, t.bbox[1])
            if edges is None:
                continue
            region = page.crop((0, top, page.width, bottom))
            for raw in words_to_rows(region.extract_words(keep_blank_chars=False), edges):
                cells = [c if c is not None else "" for c in raw]
                if not cells or not re.fullmatch(r"\d{1,4}", norm(cells[0])):
                    # continuation line of a wrapped title: append to previous row
                    if rows and cells and not norm(cells[0]) and any(norm(c) for c in cells):
                        for col, val in zip(header_cols, cells):
                            if col in ("title", "original_title", "distributor") and norm(val):
                                rows[-1][col] = norm(rows[-1].get(col, "") + " " + val)
                    continue
                rec = {}
                for col, val in zip(header_cols, cells):
                    if col and col not in rec:
                        rec[col] = norm(val)
                rows.append(rec)
    return rows


NUMERIC = {"rank", "weeks_on_release", "cinemas", "screens", "gross_eur", "admissions",
           "gross_cum_eur", "admissions_cum", "gross_pct_change", "admissions_pct_change"}


def clean(rec):
    out = {}
    for k, v in rec.items():
        out[k] = to_number(v) if k in NUMERIC else v
    if "release_date" in out:
        m = re.match(r"(\d{2})/(\d{2})/(\d{4})", out["release_date"])
        out["release_date"] = f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else ""
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    log = []
    datasets = {"weekly_top25": [], "weekly_spanish": [], "annual_spanish": []}
    # Classify by filename, not by the link label: a few links on the ICAA page are mislabelled
    # (e.g. a Spanish-films list under "Top 25") and names contain typos ("espaniol", "epaniol").
    files = []
    for pdf in sorted(RAW.glob("*/*.pdf")):
        n = pdf.name.split("_", 1)[-1].lower()
        if "internacional" in n:
            continue
        if n.startswith(("acumulado", "recaud")):
            # partial-year snapshots ("acumulado-2024-a-21-julio-2024") are superseded by the
            # full-year file, except for the current year (2026 YTD).
            if "-a-" in n and "2026" not in n:
                log.append({"category": "skipped", "file": pdf.name, "rows": 0, "period": "",
                            "error": "partial-year snapshot superseded by full-year file"})
                continue
            files.append(("annual_spanish", pdf))
        elif re.search(r"esp|epan", n):
            files.append(("weekly_spanish", pdf))
        elif "top" in n:
            files.append(("weekly_top25", pdf))
    for cat, pdf in files:
        if True:
            try:
                rows = [clean(r) for r in extract_pdf(pdf)]
                meta = {"source_file": pdf.name}
                if cat.startswith("weekly"):
                    wk = weekend_from_name(pdf.name)
                    meta["weekend_start"] = wk.isoformat() if wk else ""
                else:
                    yrs = re.findall(r"20\d\d", pdf.name.split("_", 1)[-1])
                    meta["year"] = yrs[0] if yrs else ""
                for r in rows:
                    r.update(meta)
                datasets[cat].extend(rows)
                log.append({"category": cat, "file": pdf.name, "rows": len(rows),
                            "period": meta.get("weekend_start", meta.get("year")), "error": ""})
            except Exception as e:  # noqa: BLE001
                log.append({"category": cat, "file": pdf.name, "rows": 0, "period": "", "error": repr(e)})
                print("ERR", pdf.name, e, file=sys.stderr)

    for name, rows in datasets.items():
        cols = []
        for r in rows:
            for k in r:
                if k not in cols:
                    cols.append(k)
        with (OUT / f"{name}.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        print(f"{name}: {len(rows)} rows")
    with (OUT / "extract_log.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["category", "file", "rows", "period", "error"])
        w.writeheader()
        w.writerows(log)


if __name__ == "__main__":
    main()
