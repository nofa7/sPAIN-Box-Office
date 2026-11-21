"""Step 5 (Share): generate the Power BI project (PBIP: TMDL semantic model + PBIR report).

Output: powerbi/SpainBoxOffice.pbip  (+ .SemanticModel/ and .Report/ folders)
Open SpainBoxOffice.pbip in Power BI Desktop and click Refresh: data is loaded from data/clean/.
The CSV folder is a Power Query parameter (DataFolder); change it under Transform data > Parameters
if the project is moved.
"""
import json
import shutil
import uuid
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean"
PBI = ROOT / "powerbi"
NAME = "SpainBoxOffice"
SM = PBI / f"{NAME}.SemanticModel"
RP = PBI / f"{NAME}.Report"
NS = uuid.UUID("6f1c1d1e-0000-4000-8000-5b0c0ff1ce00")
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"


def guid(*parts):
    return str(uuid.uuid5(NS, "/".join(parts)))


def wjson(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def wtext(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


# ============================================================================ semantic model
TABLES = ["dim_film", "dim_distributor", "dim_date", "fact_weekend_top25",
          "fact_weekend_spanish", "fact_annual_spanish"]
DATE_COLS = {"release_weekend", "weekend_start", "date", "release_date"}
BOOL_COLS = {"is_rerelease", "opened_in_top25", "is_friday", "admissions_imputed",
             "is_partial_year", "released_in_year"}
TEXT_COLS = {"film_id", "title", "original_title", "distributor", "origin", "release_month",
             "release_season", "opening_cinemas_band", "gross_band", "distributor_type", "quarter",
             "month", "year_month", "weekday", "season", "period", "source_file"}
NO_SUM = {"rank", "year", "release_year", "release_month_num", "month_num", "iso_week",
          "weeks_on_release", "opening_rank", "best_rank", "last_weeks_on_release",
          "gross_pct_change", "admissions_pct_change", "legs_multiple", "avg_ticket_eur",
          "opening_per_screen_eur", "opening_per_cinema_eur", "weeks_in_top25", "peak_screens",
          "opening_screens", "opening_cinemas", "cinemas", "screens"}
HIDDEN = {"source_file"}
SORT_BY = {("dim_film", "release_month"): "release_month_num", ("dim_date", "month"): "month_num"}
FORMATS = {"gross_eur": "#,0", "admissions": "#,0", "gross_cum_eur": "#,0", "admissions_cum": "#,0",
           "total_gross_eur": "#,0", "opening_gross_eur": "#,0", "total_admissions": "#,0",
           "opening_admissions": "#,0"}

T = "\t"


def col_kind(table, col, series):
    if col in DATE_COLS:
        return "dateTime", "type date"
    if col in BOOL_COLS:
        return "boolean", "type logical"
    if col in TEXT_COLS or series.dtype == object or str(series.dtype).startswith("str"):
        return "string", "type text"
    if pd.api.types.is_integer_dtype(series):
        return "int64", "Int64.Type"
    return "double", "type number"


def tmdl_name(n):
    return f"'{n}'" if any(c in n for c in " ()%-+/.") else n


MEASURES = {
    "fact_weekend_top25": [
        ("Total Gross", "SUM(fact_weekend_top25[gross_eur])", "€#,0", "Weekend box office (EUR), Top 25 films"),
        ("Total Admissions", "SUM(fact_weekend_top25[admissions])", "#,0", "Tickets sold, Top 25 films"),
        ("Avg Ticket Price", "DIVIDE([Total Gross], [Total Admissions])", "€0.00", "Gross / admissions"),
        ("Weekends", "DISTINCTCOUNT(fact_weekend_top25[weekend_start])", "#,0", "Weekends with data"),
        ("Avg Weekend Gross", "DIVIDE([Total Gross], [Weekends])", "€#,0", "Average Top 25 gross per weekend"),
        ("Films on Screen", "DISTINCTCOUNT(fact_weekend_top25[film_id])", "#,0", "Distinct films in the Top 25"),
        ("Spanish Gross", 'CALCULATE([Total Gross], dim_film[origin] = "Spanish")', "€#,0", "Gross of Spanish films"),
        ("Spanish Share", "DIVIDE([Spanish Gross], [Total Gross])", "0.0%", "Share of gross from Spanish films"),
        ("Independent Share",
         'DIVIDE(CALCULATE([Total Gross], dim_distributor[distributor_type] = "Independent"), [Total Gross])',
         "0.0%", "Share of gross released by independent distributors"),
        ("Major Studio Share",
         'DIVIDE(CALCULATE([Total Gross], dim_distributor[distributor_type] = "Major studio"), [Total Gross])',
         "0.0%", "Share of gross released by the Hollywood majors"),
        ("Gross PY", "CALCULATE([Total Gross], DATEADD(dim_date[date], -1, YEAR))", "€#,0", "Same period last year"),
        ("Gross YoY %",
         "\nVAR _prev = [Gross PY]\nRETURN\n    IF(NOT ISBLANK(_prev), DIVIDE([Total Gross] - _prev, _prev))",
         "+0.0%;-0.0%;0.0%", "Change vs same period last year"),
        ("Median Week-over-Week Change", "DIVIDE(MEDIAN(fact_weekend_top25[gross_pct_change]), 100)",
         "+0%;-0%;0%", "Median weekend-to-weekend gross change (drop rate)"),
        ("Top 10 Films Share",
         "\nVAR _top = TOPN(10, VALUES(fact_weekend_top25[film_id]), [Total Gross])\n"
         "RETURN\n    DIVIDE(CALCULATE([Total Gross], _top), [Total Gross])",
         "0.0%", "Concentration: share of gross from the 10 biggest films in context"),
    ],
    "dim_film": [
        ("New Releases",
         "COUNTROWS(FILTER(dim_film, dim_film[opened_in_top25] = TRUE() && dim_film[is_rerelease] = FALSE()))",
         "#,0", "Films that opened in the Top 25 (excl. re-releases)"),
        ("Release Gross",
         "SUMX(FILTER(dim_film, dim_film[opened_in_top25] = TRUE() && dim_film[is_rerelease] = FALSE()), dim_film[total_gross_eur])",
         "€#,0", "Lifetime gross of new releases"),
        ("Median Opening",
         "MEDIANX(FILTER(dim_film, dim_film[opened_in_top25] = TRUE() && dim_film[is_rerelease] = FALSE()), dim_film[opening_gross_eur])",
         "€#,0", "Median opening-weekend gross"),
        ("Median Film Gross",
         "MEDIANX(FILTER(dim_film, dim_film[opened_in_top25] = TRUE() && dim_film[is_rerelease] = FALSE()), dim_film[total_gross_eur])",
         "€#,0", "Median lifetime gross per new release"),
        ("Hit Rate (1M+)",
         "\nVAR _hits = COUNTROWS(FILTER(dim_film, dim_film[opened_in_top25] = TRUE() && dim_film[is_rerelease] = FALSE() && dim_film[total_gross_eur] >= 1000000))\n"
         "RETURN\n    DIVIDE(_hits, [New Releases])",
         "0.0%", "Share of new releases grossing 1M EUR or more"),
        ("Median Legs",
         "MEDIANX(FILTER(dim_film, dim_film[opened_in_top25] = TRUE() && dim_film[is_rerelease] = FALSE() && NOT ISBLANK(dim_film[legs_multiple])), dim_film[legs_multiple])",
         "0.00x", "Median lifetime gross / opening weekend"),
        ("Spanish Share of Releases",
         '\nVAR _all = CALCULATE([New Releases], REMOVEFILTERS(dim_film[origin]))\n'
         'RETURN\n    DIVIDE(CALCULATE([New Releases], dim_film[origin] = "Spanish"), _all)',
         "0.0%", "Share of new releases that are Spanish films"),
        ("Spanish Share of Release Gross",
         '\nVAR _all = CALCULATE([Release Gross], REMOVEFILTERS(dim_film[origin]))\n'
         'RETURN\n    DIVIDE(CALCULATE([Release Gross], dim_film[origin] = "Spanish"), _all)',
         "0.0%", "Share of new releases' lifetime gross earned by Spanish films"),
        ("Median Opening per Cinema",
         "MEDIANX(FILTER(dim_film, dim_film[opened_in_top25] = TRUE() && dim_film[is_rerelease] = FALSE() && NOT ISBLANK(dim_film[opening_per_cinema_eur])), dim_film[opening_per_cinema_eur])",
         "€#,0", "Median opening gross per cinema"),
    ],
    "fact_annual_spanish": [
        ("Spanish Cinema Gross", "SUM(fact_annual_spanish[gross_eur])", "€#,0",
         "All Spanish films on release in the year (ICAA annual lists)"),
        ("Spanish Cinema Admissions", "SUM(fact_annual_spanish[admissions])", "#,0", "Admissions, Spanish films"),
        ("Spanish Films on Release", "DISTINCTCOUNT(fact_annual_spanish[title])", "#,0", "Distinct Spanish titles"),
    ],
}


def table_tmdl(name):
    df = pd.read_csv(CLEAN / f"{name}.csv", nrows=5000)
    lines = [f"table {name}", f"{T}lineageTag: {guid('table', name)}", ""]
    if name == "dim_date":
        lines.insert(1, f"{T}dataCategory: Time")
    for mname, expr, fmt, desc in MEASURES.get(name, []):
        lines.append(f"{T}/// {desc}")
        if expr.startswith("\n"):
            body = "\n".join(f"{T*3}{l}" for l in expr.strip("\n").split("\n"))
            lines.append(f"{T}measure {tmdl_name(mname)} =\n{body}")
        else:
            lines.append(f"{T}measure {tmdl_name(mname)} = {expr}")
        lines += [f"{T*2}formatString: {fmt}", f"{T*2}displayFolder: KPIs",
                  f"{T*2}lineageTag: {guid('measure', name, mname)}", ""]
    types = []
    for c in df.columns:
        dt, mtype = col_kind(name, c, df[c])
        types.append((c, mtype))
        lines.append(f"{T}column {tmdl_name(c)}")
        lines.append(f"{T*2}dataType: {dt}")
        if dt == "dateTime":
            lines.append(f"{T*2}formatString: yyyy-mm-dd")
        elif c in FORMATS:
            lines.append(f"{T*2}formatString: {FORMATS[c]}")
        if name == "dim_date" and c == "date":
            lines.append(f"{T*2}isKey")
        if c in HIDDEN:
            lines.append(f"{T*2}isHidden")
        lines.append(f"{T*2}lineageTag: {guid('col', name, c)}")
        summ = "none" if (dt in ("string", "boolean", "dateTime") or c in NO_SUM) else "sum"
        lines.append(f"{T*2}summarizeBy: {summ}")
        lines.append(f"{T*2}sourceColumn: {c}")
        if (name, c) in SORT_BY:
            lines.append(f"{T*2}sortByColumn: {SORT_BY[(name, c)]}")
        lines.append("")
        lines.append(f"{T*2}annotation SummarizationSetBy = Automatic")
        if dt == "dateTime":
            lines.append("")
            lines.append(f"{T*2}annotation UnderlyingDateTimeDataType = Date")
        lines.append("")
    type_list = ", ".join(f'{{"{c}", {t}}}' for c, t in types)
    m = [
        "let",
        f'    Source = Csv.Document(File.Contents(DataFolder & "{name}.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),',
        "    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),",
        f'    Typed = Table.TransformColumnTypes(Promoted, {{{type_list}}}, "en-US")',
        "in",
        "    Typed",
    ]
    lines.append(f"{T}partition {name} = m")
    lines.append(f"{T*2}mode: import")
    lines.append(f"{T*2}source =")
    lines += [f"{T*4}{l}" for l in m]
    lines.append("")
    lines.append(f"{T}annotation PBI_ResultType = Table")
    lines.append("")
    return "\n".join(lines)


RELATIONSHIPS = [
    ("fact_weekend_top25", "film_id", "dim_film", "film_id"),
    ("fact_weekend_top25", "weekend_start", "dim_date", "date"),
    ("dim_film", "distributor", "dim_distributor", "distributor"),
    ("fact_weekend_spanish", "weekend_start", "dim_date", "date"),
    ("fact_weekend_spanish", "distributor", "dim_distributor", "distributor"),
    ("fact_annual_spanish", "distributor", "dim_distributor", "distributor"),
]


def build_model():
    d = SM / "definition"
    wjson(SM / "definition.pbism", {"version": "4.0", "settings": {}})
    wtext(d / "database.tmdl", "database\n\tcompatibilityLevel: 1600\n")
    model = ["model Model", f"{T}culture: en-US", f"{T}defaultPowerBIDataSourceVersion: powerBI_V3",
             f"{T}sourceQueryCulture: en-US", f"{T}dataAccessOptions", f"{T*2}legacyRedirects",
             f"{T*2}returnErrorValuesAsNull", "",
             "annotation __PBI_TimeIntelligenceEnabled = 0", "",
             f"annotation PBI_QueryOrder = {json.dumps(['DataFolder'] + TABLES)}", ""]
    model += [f"ref table {t}" for t in TABLES]
    wtext(d / "model.tmdl", "\n".join(model) + "\n")
    folder = str(CLEAN) + "\\"
    wtext(d / "expressions.tmdl",
          f'expression DataFolder = "{folder}" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]\n'
          f"{T}lineageTag: {guid('expr', 'DataFolder')}\n\n"
          f"{T}annotation PBI_ResultType = Text\n")
    rel = []
    for ft, fc, tt, tc in RELATIONSHIPS:
        rel += [f"relationship {guid('rel', ft, fc, tt)}", f"{T}fromColumn: {ft}.{fc}",
                f"{T}toColumn: {tt}.{tc}", ""]
    wtext(d / "relationships.tmdl", "\n".join(rel))
    for t in TABLES:
        wtext(d / "tables" / f"{t}.tmdl", table_tmdl(t))


# ============================================================================ report
def col(entity, prop):
    return {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def meas(entity, prop):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def agg_sum(entity, prop):
    # Function 0 = Sum. Used on the scatter: one point per film, so Sum = that film's value.
    return {"Aggregation": {"Expression": col(entity, prop), "Function": 0}}


M_T = "fact_weekend_top25"
M_F = "dim_film"
M_A = "fact_annual_spanish"


def proj(field, display=None):
    if "Aggregation" in field:
        inner = field["Aggregation"]["Expression"]["Column"]
        ent, prop = inner["Expression"]["SourceRef"]["Entity"], inner["Property"]
        p = {"field": field, "queryRef": f"Sum({ent}.{prop})", "nativeQueryRef": f"Sum of {prop}"}
        if display:
            p["displayName"] = display
        return p
    kind = "Measure" if "Measure" in field else "Column"
    ent = field[kind]["Expression"]["SourceRef"]["Entity"]
    prop = field[kind]["Property"]
    p = {"field": field, "queryRef": f"{ent}.{prop}", "nativeQueryRef": prop}
    if display:
        p["displayName"] = display
    return p


def lit(v):
    if isinstance(v, bool):
        return {"expr": {"Literal": {"Value": "true" if v else "false"}}}
    if isinstance(v, (int, float)):
        return {"expr": {"Literal": {"Value": f"{v}D"}}}
    return {"expr": {"Literal": {"Value": f"'{v}'"}}}


def title_obj(text):
    return {"title": [{"properties": {"show": lit(True), "text": lit(text)}}]}


class Page:
    def __init__(self, pid, display):
        self.pid, self.display, self.visuals, self.z = pid, display, [], 0

    def add(self, vid, vtype, x, y, w, h, roles=None, title=None, sort=None, objects=None,
            container_objects=None):
        v = {"visualType": vtype, "drillFilterOtherVisuals": True}
        if roles:
            v["query"] = {"queryState": {r: {"projections": [proj(*f) if isinstance(f, tuple) else proj(f)
                                                             for f in fs]}
                                         for r, fs in roles.items()}}
            if sort:
                field, direction = sort
                v["query"]["sortDefinition"] = {"sort": [{"field": field, "direction": direction}],
                                                "isDefaultSort": False}
        if objects:
            v["objects"] = objects
        vco = {}
        if title:
            vco.update(title_obj(title))
        if container_objects:
            vco.update(container_objects)
        if vco:
            v["visualContainerObjects"] = vco
        self.z += 1000
        self.visuals.append({
            "$schema": f"{SCHEMA}/visualContainer/2.4.0/schema.json",
            "name": vid,
            "position": {"x": x, "y": y, "z": self.z, "width": w, "height": h, "tabOrder": self.z},
            "visual": v,
        })

    def text(self, vid, x, y, w, h, text, size=20, bold=True, color="#1F2A44"):
        # one paragraph per line; the first line of a multi-line box is bold (a heading)
        lines = text.split("\n")
        objects = {"general": [{"properties": {"paragraphs": [
            {"textRuns": [{"value": line, "textStyle": {
                "fontSize": f"{size}pt",
                "fontWeight": "bold" if (bold or (len(lines) > 1 and i == 0)) else "normal",
                "color": color}}]} for i, line in enumerate(lines)]}}]}
        self.z += 1000
        self.visuals.append({
            "$schema": f"{SCHEMA}/visualContainer/2.4.0/schema.json",
            "name": vid,
            "position": {"x": x, "y": y, "z": self.z, "width": w, "height": h, "tabOrder": self.z},
            "visual": {"visualType": "textbox", "objects": objects, "drillFilterOtherVisuals": True},
        })

    def card(self, vid, x, y, w, h, measure, label):
        self.add(vid, "card", x, y, w, h, {"Values": [(measure, label)]}, title=None,
                 objects={"categoryLabels": [{"properties": {"show": lit(True)}}]})

    def slicer(self, vid, x, y, w, h, field, title, min_value=None):
        # slicer header shows the field's display name; no container title (avoids "Year / year")
        self.add(vid, "slicer", x, y, w, h, {"Values": [(field, title)]},
                 objects={"data": [{"properties": {"mode": lit("Dropdown")}}]})
        if min_value is not None:
            # visual-level filter: hides options < min_value from the slicer list without
            # filtering the data when nothing is selected (2019 films on release in early 2020
            # still count in the totals)
            ent = field["Column"]["Expression"]["SourceRef"]["Entity"]
            prop = field["Column"]["Property"]
            self.visuals[-1]["filterConfig"] = {"filters": [{
                "name": f"{vid}_min",
                "field": field,
                "type": "Advanced",
                "filter": {
                    "Version": 2,
                    "From": [{"Name": "t", "Entity": ent, "Type": 0}],
                    "Where": [{"Condition": {"Comparison": {
                        "ComparisonKind": 1,  # GreaterThan
                        "Left": {"Column": {"Expression": {"SourceRef": {"Source": "t"}}, "Property": prop}},
                        "Right": {"Literal": {"Value": f"{min_value}L"}}}}}],
                },
            }]}

    def year_slicer(self, vid, x, y, w, h, field, title):
        self.slicer(vid, x, y, w, h, field, title, min_value=2019)  # year > 2019


def build_pages():
    pages = []
    FOOT = ("Source: ICAA / Ministerio de Cultura, weekly Top 25 box office (Comscore-Rentrak), "
            "Jan 2020 - Nov 2026. 2026 = year to date.")

    # ------------------------------------------------------------------ 1. Market overview
    p = Page("p1market", "1. Market Overview")
    p.text("title", 24, 8, 900, 50, "Spain Box Office 2020-2026: Market Overview")
    p.text("sub", 24, 54, 1000, 38, "How big is the theatrical market, how fast has it recovered, "
                                     "and who takes the money?", size=11, bold=False, color="#5B6478")
    p.year_slicer("s_year", 1040, 12, 216, 70, col("dim_date", "year"), "Year")
    kpis = [("Total Gross", "Box office (Top 25)"), ("Total Admissions", "Admissions"),
            ("Avg Ticket Price", "Avg ticket"), ("Spanish Share", "Spanish films share"),
            ("Independent Share", "Independent distributors share")]
    for i, (m, lbl) in enumerate(kpis):
        p.card(f"kpi{i}", 24 + i * 248, 96, 236, 96, meas(M_T, m), lbl)
    p.add("c_year_origin", "columnChart", 24, 208, 616, 300,
          {"Category": [col("dim_date", "year")], "Y": [meas(M_T, "Total Gross")],
           "Series": [col("dim_film", "origin")]},
          title="Annual box office by film origin (Top 25 films)")
    p.add("c_month_line", "lineChart", 656, 208, 600, 300,
          {"Category": [col("dim_date", "year_month")], "Y": [meas(M_T, "Avg Weekend Gross")]},
          title="Average weekend gross by month: COVID collapse and recovery")
    p.add("c_disttype", "donutChart", 24, 520, 300, 176,
          {"Category": [col("dim_distributor", "distributor_type")], "Y": [meas(M_T, "Total Gross")]},
          title="Gross by distributor type")
    p.add("c_conc", "lineChart", 340, 520, 450, 176,
          {"Category": [col("dim_date", "year")], "Y": [meas(M_T, "Top 10 Films Share")]},
          title="Concentration: share of gross from the year's top 10 films")
    p.add("c_ticket", "lineChart", 806, 520, 450, 176,
          {"Category": [col("dim_date", "year")], "Y": [meas(M_T, "Avg Ticket Price")]},
          title="Average ticket price (EUR)")
    p.text("foot", 24, 690, 1232, 30, FOOT, size=8, bold=False, color="#8A93A6")
    pages.append(p)

    # ------------------------------------------------------------------ 2. Seasonality & timing
    p = Page("p2timing", "2. Release Timing")
    p.text("title", 24, 8, 900, 50, "When to release: seasonality and release windows")
    p.text("sub", 24, 54, 1000, 38, "Demand peaks in July and December; Christmas and October releases "
                                     "earn the most per film.", size=11, bold=False, color="#5B6478")
    p.slicer("s_origin", 820, 12, 210, 70, col("dim_film", "origin"), "Film origin")
    p.year_slicer("s_ryear", 1046, 12, 210, 70, col("dim_film", "release_year"), "Release year")
    p.add("c_season_dem", "clusteredColumnChart", 24, 96, 616, 290,
          {"Category": [col("dim_date", "month")], "Y": [meas(M_T, "Avg Weekend Gross")]},
          title="Demand: average Top 25 weekend gross by calendar month")
    p.add("c_rel_month", "clusteredColumnChart", 656, 96, 600, 290,
          {"Category": [col("dim_film", "release_month")], "Y": [meas(M_F, "Median Film Gross")]},
          title="Median lifetime gross of films released in each month")
    p.add("m_season", "pivotTable", 24, 400, 760, 296,
          {"Rows": [col("dim_film", "release_season")], "Columns": [col("dim_film", "origin")],
           "Values": [meas(M_F, "New Releases"), meas(M_F, "Median Film Gross"),
                      meas(M_F, "Hit Rate (1M+)"), meas(M_F, "Median Legs")]},
          title="Release window scorecard (new releases)")
    p.add("c_hit_month", "clusteredColumnChart", 800, 400, 456, 296,
          {"Category": [col("dim_film", "release_month")], "Y": [meas(M_F, "Hit Rate (1M+)")]},
          title="Hit rate (1M EUR+) by release month")
    p.text("foot", 24, 690, 1232, 30, FOOT, size=8, bold=False, color="#8A93A6")
    pages.append(p)

    # ------------------------------------------------------------------ 3. Spanish vs foreign
    p = Page("p3origin", "3. Spanish Cinema")
    p.text("title", 24, 8, 900, 50, "Spanish vs foreign films: is local content a good bet?")
    p.text("sub", 24, 54, 1000, 38, "Spanish films match foreign ones on median gross and hold better "
                                     "after week 4, but hits are rarer and concentrated.",
           size=11, bold=False, color="#5B6478")
    p.year_slicer("s_ryear", 1046, 12, 210, 70, col("dim_film", "release_year"), "Release year")
    p.add("m_origin", "tableEx", 24, 96, 616, 150,
          {"Values": [col("dim_film", "origin"), meas(M_F, "New Releases"), meas(M_F, "Median Opening"),
                      meas(M_F, "Median Film Gross"), meas(M_F, "Hit Rate (1M+)"), meas(M_F, "Median Legs")]},
          title="Scorecard by origin (new releases)")
    p.add("c_decay", "lineChart", 656, 96, 600, 290,
          {"Category": [col("fact_weekend_top25", "weeks_on_release")],
           "Y": [meas(M_T, "Median Week-over-Week Change")], "Series": [col("dim_film", "origin")]},
          title="Weekly drop rate by week on release (lower drop = longer legs)")
    p.add("c_annual", "clusteredColumnChart", 24, 260, 616, 236,
          {"Category": [col(M_A, "year")], "Y": [meas(M_A, "Spanish Cinema Gross")]},
          title="Spanish cinema box office 2016-2026 (all Spanish films, ICAA annual)")
    p.add("t_top_es", "tableEx", 656, 400, 600, 296,
          {"Values": [col("dim_film", "title"), col("dim_film", "distributor"),
                      col("dim_film", "release_year"), col("dim_film", "origin"),
                      (col("dim_film", "total_gross_eur"), "Total gross (EUR)")]},
          title="Biggest films (filter by origin with the slicer)",
          sort=(col("dim_film", "total_gross_eur"), "Descending"))
    p.slicer("s_origin", 24, 510, 300, 70, col("dim_film", "origin"), "Film origin")
    p.card("k_share", 340, 510, 300, 90, meas(M_T, "Spanish Share"), "Spanish share of Top 25 gross")
    p.text("note", 24, 612, 616, 80, "Spanish share swings with a handful of hits (e.g. the Padre no hay "
                                      "más que uno saga, Torrente, La bola negra). Annual figures cover every "
                                      "Spanish film, not only Top 25 entries.", size=9, bold=False,
           color="#5B6478")
    p.text("foot", 24, 690, 1232, 30, FOOT, size=8, bold=False, color="#8A93A6")
    pages.append(p)

    # ------------------------------------------------------------------ 3b. Spanish vs foreign (Q3 cont.)
    p = Page("p3bversus", "3b. Spanish vs Foreign")
    p.text("title", 24, 8, 900, 50, "Spanish vs foreign releases: volume, width and who releases them")
    p.text("sub", 24, 54, 1000, 38, "Spanish films are ~27% of releases but ~17% of gross: they match "
                                     "foreign films at equal width, yet rarely get opened wide.",
           size=11, bold=False, color="#5B6478")
    p.year_slicer("s_ryear", 1046, 12, 210, 70, col("dim_film", "release_year"), "Release year")
    p.card("k_rel", 24, 96, 300, 90, meas(M_F, "Spanish Share of Releases"), "Spanish share of new releases")
    p.card("k_gross", 340, 96, 300, 90, meas(M_F, "Spanish Share of Release Gross"),
           "Spanish share of release gross")
    p.add("c_shares", "clusteredColumnChart", 24, 200, 616, 270,
          {"Category": [(col("dim_film", "release_year"), "Release year")],
           "Y": [meas(M_F, "Spanish Share of Releases"), meas(M_F, "Spanish Share of Release Gross")]},
          title="Spanish films: share of releases vs share of gross")
    p.add("m_width_origin", "pivotTable", 656, 96, 600, 300,
          {"Rows": [(col("dim_film", "opening_cinemas_band"), "Opening width (cinemas)")],
           "Columns": [col("dim_film", "origin")],
           "Values": [meas(M_F, "New Releases"), meas(M_F, "Median Film Gross"), meas(M_F, "Hit Rate (1M+)")]},
          title="Same opening width, different origin")
    p.add("m_dist_origin", "pivotTable", 656, 410, 600, 276,
          {"Rows": [col("dim_distributor", "distributor_type")], "Columns": [col("dim_film", "origin")],
           "Values": [meas(M_F, "New Releases"), meas(M_F, "Release Gross"), meas(M_F, "Hit Rate (1M+)")]},
          title="Who releases Spanish films? Majors vs independents")
    p.text("note", 24, 484, 616, 200,
           "Key takeaways (2022-2026 new releases)\n"
           "- Up to 249 cinemas, Spanish films earn as much as or more than foreign ones; above 250 they "
           "earn less per cinema but hold longer (legs 4.8x vs 4.0x at 325+ cinemas).\n"
           "- Majors release only ~23% of Spanish films but take ~61% of their gross.\n"
           "- Independents take ~39% of Spanish-film gross vs ~13% of foreign-film gross: Spanish cinema "
           "is where independents really compete.", size=10, bold=False, color="#1F2A44")
    p.text("foot", 24, 690, 1232, 30, FOOT, size=8, bold=False, color="#8A93A6")
    pages.append(p)

    # ------------------------------------------------------------------ 4. Distributors
    p = Page("p4dist", "4. Distributors")
    p.text("title", 24, 8, 900, 50, "Distributor benchmark: majors vs independents")
    p.text("sub", 24, 54, 1000, 38, "Majors take ~80% of the Top 25 gross; the best independents win "
                                     "with fewer, wider bets.", size=11, bold=False, color="#5B6478")
    p.slicer("s_type", 820, 12, 210, 70, col("dim_distributor", "distributor_type"), "Distributor type")
    p.year_slicer("s_ryear", 1046, 12, 210, 70, col("dim_film", "release_year"), "Release year")
    p.add("t_league", "tableEx", 24, 96, 760, 600,
          {"Values": [col("dim_film", "distributor"), meas(M_F, "New Releases"), meas(M_F, "Release Gross"),
                      meas(M_F, "Median Film Gross"), meas(M_F, "Hit Rate (1M+)"), meas(M_F, "Median Legs")]},
          title="League table (new releases in selected years)",
          sort=(meas(M_F, "Release Gross"), "Descending"))
    p.add("c_share_year", "columnChart", 800, 96, 456, 290,
          {"Category": [col("dim_date", "year")], "Y": [meas(M_T, "Total Gross")],
           "Series": [col("dim_distributor", "distributor_type")]},
          title="Gross by distributor type and year")
    p.add("c_indie", "clusteredBarChart", 800, 400, 456, 296,
          {"Category": [col("dim_film", "distributor")], "Y": [meas(M_F, "Hit Rate (1M+)")]},
          title="Hit rate by distributor",
          sort=(meas(M_F, "Hit Rate (1M+)"), "Descending"))
    p.text("foot", 24, 690, 1232, 30, FOOT, size=8, bold=False, color="#8A93A6")
    pages.append(p)

    # ------------------------------------------------------------------ 5. Release width
    p = Page("p5width", "5. Release Strategy")
    p.text("title", 24, 8, 900, 50, "Release width: how many cinemas to open in?")
    p.text("sub", 24, 54, 1000, 38, "Above ~250 cinemas, films earn more per venue and hold longer: "
                                     "width signals confidence and buys marketing visibility.",
           size=11, bold=False, color="#5B6478")
    p.slicer("s_origin", 820, 12, 210, 70, col("dim_film", "origin"), "Film origin")
    p.year_slicer("s_ryear", 1046, 12, 210, 70, col("dim_film", "release_year"), "Release year")
    p.add("c_band_gross", "clusteredColumnChart", 24, 96, 616, 290,
          {"Category": [(col("dim_film", "opening_cinemas_band"), "Opening width (cinemas)")],
           "Y": [meas(M_F, "Median Film Gross")]},
          title="Median lifetime gross by opening width (cinemas)")
    p.add("c_band_hit", "clusteredColumnChart", 656, 96, 600, 290,
          {"Category": [(col("dim_film", "opening_cinemas_band"), "Opening width (cinemas)")],
           "Y": [meas(M_F, "Hit Rate (1M+)")]},
          title="Hit rate (1M EUR+) by opening width")
    p.add("sc_width", "scatterChart", 24, 400, 760, 296,
          {"Category": [col("dim_film", "title")],
           "X": [(agg_sum("dim_film", "opening_cinemas"), "Opening cinemas")],
           "Y": [(agg_sum("dim_film", "total_gross_eur"), "Lifetime gross")],
           "Series": [col("dim_film", "origin")]},
          title="Every film: opening cinemas vs lifetime gross")
    p.add("t_band", "tableEx", 800, 400, 456, 296,
          {"Values": [col("dim_film", "opening_cinemas_band"), meas(M_F, "New Releases"),
                      meas(M_F, "Median Opening per Cinema"), meas(M_F, "Hit Rate (1M+)")]},
          title="Width bands summary")
    p.text("foot", 24, 690, 1232, 30, FOOT, size=8, bold=False, color="#8A93A6")
    pages.append(p)
    return pages


THEME = {
    "name": "SpainBoxOffice",
    "dataColors": ["#C8102E", "#1F2A44", "#F2A900", "#5B8DB8", "#7A9E7E", "#B07AA1", "#8A93A6",
                   "#E07B53"],
    "background": "#FFFFFF", "foreground": "#1F2A44", "tableAccent": "#C8102E",
    "good": "#2E7D32", "neutral": "#F2A900", "bad": "#C8102E",
    "textClasses": {"title": {"fontFace": "Segoe UI Semibold", "fontSize": 12, "color": "#1F2A44"},
                    "callout": {"fontFace": "Segoe UI Semibold", "fontSize": 24, "color": "#1F2A44"},
                    "label": {"fontFace": "Segoe UI", "fontSize": 10, "color": "#5B6478"}},
}


def build_report():
    d = RP / "definition"
    wjson(RP / "definition.pbir", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0",
        "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}}})
    # base theme copied from the local Power BI Desktop install, plus our custom theme
    import subprocess
    loc = subprocess.run(["powershell", "-NoProfile", "-Command",
                          "(Get-AppxPackage Microsoft.MicrosoftPowerBIDesktop).InstallLocation"],
                         capture_output=True, text=True).stdout.strip()
    base = Path(loc) / "bin" / "WebView2Resources" / "minerva" / "sharedresources" / "BaseThemes" / "CY24SU10.json"
    dst = RP / "StaticResources" / "SharedResources" / "BaseThemes" / "CY24SU10.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(base, dst)
    wjson(RP / "StaticResources" / "RegisteredResources" / "SpainBoxOffice.json", THEME)
    ver = {"visual": "2.4.0", "report": "3.0.0", "page": "2.0.0"}
    wjson(d / "report.json", {
        "$schema": f"{SCHEMA}/report/3.0.0/schema.json",
        "themeCollection": {
            "baseTheme": {"name": "CY24SU10", "reportVersionAtImport": ver, "type": "SharedResources"},
            "customTheme": {"name": "SpainBoxOffice.json", "reportVersionAtImport": ver,
                            "type": "RegisteredResources"}},
        "resourcePackages": [
            {"name": "SharedResources", "type": "SharedResources",
             "items": [{"name": "CY24SU10", "path": "BaseThemes/CY24SU10.json", "type": "BaseTheme"}]},
            {"name": "RegisteredResources", "type": "RegisteredResources",
             "items": [{"name": "SpainBoxOffice.json", "path": "SpainBoxOffice.json", "type": "CustomTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True, "defaultDrillFilterOtherVisuals": True,
                     "allowChangeFilterTypes": True, "useEnhancedTooltips": True},
    })
    wjson(d / "version.json", {"$schema": f"{SCHEMA}/versionMetadata/1.0.0/schema.json", "version": "2.0.0"})
    pages = build_pages()
    wjson(d / "pages" / "pages.json", {"$schema": f"{SCHEMA}/pagesMetadata/1.0.0/schema.json",
                                       "pageOrder": [p.pid for p in pages], "activePageName": pages[0].pid})
    for p in pages:
        wjson(d / "pages" / p.pid / "page.json", {
            "$schema": f"{SCHEMA}/page/2.0.0/schema.json", "name": p.pid, "displayName": p.display,
            "displayOption": "FitToPage", "height": 720, "width": 1280})
        for v in p.visuals:
            wjson(d / "pages" / p.pid / "visuals" / v["name"] / "visual.json", v)


def main():
    for pth in (SM, RP):
        if pth.exists():
            shutil.rmtree(pth)
    build_model()
    build_report()
    wjson(PBI / f"{NAME}.pbip", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0", "artifacts": [{"report": {"path": f"{NAME}.Report"}}],
        "settings": {"enableAutoRecovery": True}})
    wtext(PBI / ".gitignore", "**/.pbi/localSettings.json\n**/.pbi/cache.abf\n")
    print(f"Power BI project written to {PBI}")


if __name__ == "__main__":
    main()
