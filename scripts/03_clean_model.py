"""Step 3 (Process): clean the extracted tables and build a star schema for Power BI.

Inputs : data/interim/{weekly_top25,weekly_spanish,annual_spanish}.csv
Outputs: data/clean/
  dim_film.csv              one row per film release (Top 25 films, 2020-2026)
  dim_distributor.csv       canonical distributor + type (Major studio / Independent)
  dim_date.csv              calendar 2016-2026 with weekend, season and holiday flags
  fact_weekend_top25.csv    film x weekend (Top 25 in Spain)
  fact_weekend_spanish.csv  Spanish film x weekend (all Spanish films on release)
  fact_annual_spanish.csv   Spanish film x calendar year (2016-2026 YTD)
  data_quality_report.md    checks run and their results
"""
import re
import unicodedata
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INTERIM = ROOT / "data" / "interim"
CLEAN = ROOT / "data" / "clean"

# --------------------------------------------------------------------------- distributors
DISTRIBUTOR_MAP = {
    # majors
    "WBI": "Warner Bros", "WARNER BROS": "Warner Bros", "WARNER BROS INT'L": "Warner Bros",
    "UPI": "Universal", "UNIVERSAL": "Universal", "UNIVERSAL INT'L": "Universal",
    "DISNEY": "Walt Disney", "WALT DISNEY": "Walt Disney",
    "FOX": "20th Century Fox",
    "SONY": "Sony",
    "PPI": "Paramount", "PARAMOUNT INT'L": "Paramount", "PARAMOUNT": "Paramount",
    "AMAZON MGM STUDIOS": "Amazon MGM",
    # independents: codes used in the annual ICAA files -> names used in the weekly files
    "ACONTRA": "A Contracorriente", "A CONTRACORRIENTE": "A Contracorriente",
    "ALFAPICT": "Alfa Pictures", "AVALON": "Avalon", "AVALON DISTRIBUCIÓN": "Avalon",
    "WANDA - AVALON": "Wanda / Avalon", "WANDA": "Wanda",
    "DEAPLANETA": "DeAPlaneta", "FILMAX": "Filmax", "SYLDAVIA": "Syldavia",
    "SUPER8": "Super 8", "SUPER 8": "Super 8", "MARGENES": "Márgenes",
    "MARGENES DISTRIBUCION": "Márgenes", "BARTON": "Barton", "SHER": "Sherlock",
    "SHERLOCK": "Sherlock", "EURODF": "European Dreams Factory",
    "DIAMOND": "Diamond Films", "DIAMOND FILMS": "Diamond Films",
    "CARAMEL": "Caramel Films", "CARAMEL FILMS": "Caramel Films",
    "VERTIGO": "Vertigo Films", "VERTIGO FILMS": "Vertigo Films",
    "BTEAM": "Bteam Pictures", "BTEAM PICTURES": "Bteam Pictures",
    "TRI": "Tri Pictures", "TRIPICTURES": "Tri Pictures", "TRI PICTURES": "Tri Pictures",
    "EONE": "eOne", "ENTERTAINMENT ONE FILMS": "eOne",
    "YOUPLANET PICTURES": "Youplanet", "YOUPLANET DISTRIBUTION": "Youplanet",
    "39 ESC": "39 Escalones", "ATERA": "Atera Films", "AVENTURA": "Aventura Cine",
    "BEGIN AGAIN": "Begin Again Films", "FLINS": "Flins y Piniculas",
    "VERDIG": "Version Digital", "VERCINE": "Vercine", "VERTICE": "Vertice",
    "KARMA": "Karma", "GOLEM": "Golem", "NUMAX": "Numax", "EMON": "Emon",
    "YEDRA": "Yedra", "SURTSEY": "Surtsey Films", "SUMMER": "Summer Films",
    "SPLENDOR": "Splendor Films", "SEVEN": "Seven Film", "NANOUK": "Nanouk Films",
    "INFINITO": "Infinito mas uno", "URRESTI": "Urresti Producciones",
    "FESTIVAL": "Festival Films", "PROYECFILM": "Proyecfilm", "CINEMARAN": "Cinemaran",
    "CAPRICCI": "Capricci Cine", "PACK": "ConUnPack", "VRSUS": "Versus Entertainment",
    "RITA&LUCA": "Rita & Luca", "BETTA": "Betta Pictures",
    "SELECTAVISIÓN": "SelectaVisión",
    "INDP": "Self-distributed", "INDEPENDENT": "Self-distributed",
    "INDEPENDENT SPAIN": "Self-distributed", "INDIE": "Self-distributed",
}
MAJORS = {"Warner Bros", "Universal", "Walt Disney", "20th Century Fox", "Sony", "Paramount", "Amazon MGM"}

# Rows where overlapping PDF text garbled the columns (verified by hand against the PDFs).
GARBLED_FIXES = {
    "Aves de presa": ("Birds of Prey (and the Fantabulous Emancipation of One Harley Quinn)", "Warner Bros"),
    "My hero academia: El despertar": ("Boku no Hero Academia: Heroes Rising", "SelectaVisión"),
    "Psycho-Pass Providence": ("Psycho-Pass: Providence", "Sony"),
    "Shin Chan en Australia": ("Kureyon Shinchan: Shinkon Ryoko Hariken", "Alfa Pictures"),
    "Shin Chan: El Superheroe": ("Crayon Shin-chan the Movie: Battle of Supernatural Powers", "Alfa Pictures"),
    "Guardianes de la noche: Rumbo a la aldea": ("Kimetsu no Yaiba: Katanakaji no Sato-hen", "Sony"),
    "E.T. El Extraterrestre 35": ("E.T. The Extra-Terrestrial 35th Anniversary", "Universal"),
}

ARTICLES = r"(The|A|An|El|La|Los|Las|Lo|Un|Una|Le|Les|L'|Il|Der|Die|Das)"


def canon_distributor(name):
    if not isinstance(name, str) or not name.strip():
        return "Unknown"
    key = re.sub(r"\s+", " ", name.strip()).upper()
    if key in DISTRIBUTOR_MAP:
        return DISTRIBUTOR_MAP[key]
    return name.strip() if name != name.upper() else name.strip().title()


def display_title(t):
    """Rentrak style 'Working Man, A' / 'Brujas, Las (de Roald Dahl)' -> 'A Working Man' ..."""
    if not isinstance(t, str):
        return t
    t = re.sub(r"\s+", " ", t).strip().replace(" :", ":")
    m = re.match(rf"^(.*?),\s*{ARTICLES}(\s*\(.*\))?$", t)
    if m:
        art = m.group(2)
        sep = "" if art.endswith("'") else " "
        t = f"{art}{sep}{m.group(1)}{m.group(3) or ''}"
    return t


def key(t):
    """Matching key: unaccented, lowercase, alphanumerics only, articles normalised."""
    t = display_title(t) or ""
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    t = re.sub(rf"^{ARTICLES.lower()}\s+", "", t)
    return re.sub(r"[^a-z0-9]", "", t)


# --------------------------------------------------------------------------- calendar
def easter(y):
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(y, month, day)


def season(d):
    e = easter(d.year)
    if (d.month == 12 and d.day >= 15) or (d.month == 1 and d.day <= 6):
        return "Christmas"
    if e - timedelta(days=9) <= d <= e + timedelta(days=1):
        return "Easter"
    if d.month in (7, 8):
        return "Summer"
    if d.month in (10, 11) or (d.month == 12):
        return "Autumn"
    if d.month in (1, 2, 3):
        return "Winter"
    if d.month in (4, 5, 6):
        return "Spring"
    return "Autumn"  # September


def build_dim_date():
    days = pd.date_range("2016-01-01", "2026-12-31", freq="D")
    df = pd.DataFrame({"date": days})
    df["year"] = df.date.dt.year
    df["quarter"] = "Q" + df.date.dt.quarter.astype(str)
    df["month_num"] = df.date.dt.month
    df["month"] = df.date.dt.strftime("%b")
    df["year_month"] = df.date.dt.strftime("%Y-%m")
    df["iso_week"] = df.date.dt.isocalendar().week.astype(int)
    df["weekday"] = df.date.dt.day_name()
    df["is_friday"] = df.date.dt.day_of_week == 4
    df["season"] = [season(d.date()) for d in df.date]
    df["period"] = pd.cut(df.date, [pd.Timestamp("2000-01-01"), pd.Timestamp("2020-03-13"),
                                    pd.Timestamp("2021-12-31"), pd.Timestamp("2100-01-01")],
                          labels=["Pre-COVID", "COVID (2020-21)", "Post-COVID (2022+)"]).astype(str)
    df["date"] = df.date.dt.date
    return df


# --------------------------------------------------------------------------- main
def main():
    CLEAN.mkdir(parents=True, exist_ok=True)
    qa = []

    t = pd.read_csv(INTERIM / "weekly_top25.csv")
    s = pd.read_csv(INTERIM / "weekly_spanish.csv")
    a = pd.read_csv(INTERIM / "annual_spanish.csv")
    qa.append(f"Raw rows: weekly_top25={len(t)}, weekly_spanish={len(s)}, annual_spanish={len(a)}")

    # --- fix garbled rows
    n_fixed = 0
    for prefix, (orig, dist) in GARBLED_FIXES.items():
        m = t.title.str.startswith(prefix, na=False)
        n_fixed += int(m.sum())
        t.loc[m, ["original_title", "distributor"]] = [orig, dist]
    qa.append(f"Garbled PDF rows fixed by hand (overlapping text): {n_fixed}")

    for df in (t, s, a):
        df["distributor"] = df.distributor.map(canon_distributor)
        df["title"] = df.title.map(display_title)
    t["original_title"] = t.original_title.map(display_title)

    # --- weekly: types, release date, dedupe
    for df in (t, s):
        df["weekend_start"] = pd.to_datetime(df.weekend_start)
        df["release_weekend"] = df.weekend_start - pd.to_timedelta((df.weeks_on_release - 1) * 7, unit="D")
        before = len(df)
        df.drop(df[df.duplicated(subset=["weekend_start", "title", "distributor"])].index, inplace=True)
        qa.append(f"Duplicate film-weekend rows dropped: {before - len(df)}")
        # opening week: cumulative must equal at least the weekend figure (one source typo)
        wk1 = df.weeks_on_release.eq(1)
        for v, c in (("gross_eur", "gross_cum_eur"), ("admissions", "admissions_cum")):
            bad = wk1 & (df[c] < df[v])
            df.loc[bad, c] = df.loc[bad, v]

    # --- admissions errors in the source PDFs (e.g. 3-5 Feb 2023: admissions truncated;
    # 14-16 Jun 2024: admissions column repeated from row 7). Detect via implied ticket price and
    # impute admissions = this week's cumulative - previous week's cumulative for the same film.
    for name, df in (("top25", t), ("spanish", s)):
        df["ticket"] = df.gross_eur / df.admissions
        file_med = df.groupby("source_file").ticket.transform("median")
        # row rule only for meaningful grosses: tiny festival/one-off screenings (e.g. 17 EUR, 1 viewer)
        # legitimately have odd averages
        suspect = (~file_med.between(4, 12)) | ((~df.ticket.between(3, 30)) & df.gross_eur.ge(2000))
        df.sort_values(["title", "weekend_start"], inplace=True)
        prev_cum = df.groupby("title").admissions_cum.shift(1)
        prev_wk = df.groupby("title").weeks_on_release.shift(1)
        consecutive = prev_wk.eq(df.weeks_on_release - 1)
        imputed = df.admissions_cum - prev_cum
        imputed = imputed.where(consecutive, df.admissions_cum.where(df.weeks_on_release.eq(1)))
        ok = suspect & imputed.gt(0) & (df.gross_eur / imputed).between(3, 30)
        df["admissions_imputed"] = False
        df.loc[ok, "admissions"] = imputed[ok]
        df.loc[ok, "admissions_imputed"] = True
        # fallback: estimate from the median ticket price of the clean rows of that weekend
        still = suspect & ~ok
        wk_ticket = (df[~suspect].assign(tk=lambda d: d.gross_eur / d.admissions)
                     .groupby("weekend_start").tk.median())
        est = (df.gross_eur / df.weekend_start.map(wk_ticket)).round()
        df.loc[still, "admissions"] = est[still]
        df.loc[still, "admissions_imputed"] = True
        qa.append(f"{name}: suspicious admissions values={int(suspect.sum())}, imputed from cumulative="
                  f"{int(ok.sum())}, estimated from weekend median ticket price={int(still.sum())}")
        df.drop(columns="ticket", inplace=True)
    # cinemas/screens: screens missing in some 2020-21 files -> leave null (not zero)
    qa.append(f"Top25 rows with missing screens (left null): {int(t.screens.isna().sum())}")

    # --- film identity (Top 25): rows are linked if they share the original-title key OR the
    # Spanish-title key (titles are spelled inconsistently between weeks, e.g. "Inside Out 2" vs
    # "Del Reves 2 (Inside out 2)"); then split by release date so re-releases/remakes stay separate.
    t = t.reset_index(drop=True)
    t["okey"] = t.original_title.map(key)
    t["tkey"] = t.title.map(key)
    parent = list(range(len(t)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for col in ("okey", "tkey"):
        for idx in t.groupby(col).indices.values():
            r0 = find(idx[0])
            for j in idx[1:]:
                parent[find(j)] = r0
    t["comp"] = [find(i) for i in range(len(t))]
    t = t.sort_values(["comp", "release_weekend"])
    gap = t.groupby("comp").release_weekend.diff().dt.days
    t["cluster"] = (gap.isna() | (gap > 56)).cumsum()
    qa.append(f"Distinct original-title keys: {t.okey.nunique()}; film releases after title linking: "
              f"{t.cluster.nunique()}")
    film = (t.groupby("cluster")
              .agg(title=("title", lambda x: x.mode().iat[0]),
                   original_title=("original_title", lambda x: x.mode().iat[0]),
                   distributor=("distributor", lambda x: x.mode().iat[0]),
                   release_weekend=("release_weekend", lambda x: x.mode().min()),
                   first_week_seen=("weeks_on_release", "min"),
                   weeks_in_top25=("weekend_start", "nunique"),
                   last_weeks_on_release=("weeks_on_release", "max"),
                   total_gross_eur=("gross_cum_eur", "max"),
                   total_admissions=("admissions_cum", "max"),
                   peak_screens=("screens", "max"),
                   peak_cinemas=("cinemas", "max"),
                   best_rank=("rank", "min"))
              .reset_index())
    op = (t[t.weeks_on_release == 1]
          .groupby("cluster").agg(opening_gross_eur=("gross_eur", "sum"),
                                  opening_admissions=("admissions", "sum"),
                                  opening_screens=("screens", "max"),
                                  opening_cinemas=("cinemas", "max"),
                                  opening_rank=("rank", "min")))
    film = film.merge(op, on="cluster", how="left")
    film["is_rerelease"] = film.title.str.contains(r"\(re\b|\(re:|reestreno|aniversario|anniversary|\(\d{4}\)",
                                                   case=False, regex=True)
    film["opened_in_top25"] = film.first_week_seen.eq(1)

    # --- Spanish origin: film appears in the ICAA "Spanish films on release" list or annual list
    s["tkey"] = s.title.map(key)
    a["tkey"] = a.title.map(key)
    t["tkey"] = t.title.map(key)
    sp_pairs = set(zip(s.tkey, s.weekend_start))
    t["is_spanish_row"] = [(k, w) in sp_pairs for k, w in zip(t.tkey, t.weekend_start)]
    sp_film = t.groupby("cluster").is_spanish_row.any()
    film["is_spanish"] = film.cluster.map(sp_film)
    # fallback: title in annual Spanish list with a release date within 120 days
    a["release_date"] = pd.to_datetime(a.release_date, errors="coerce")
    ann_rel = a.dropna(subset=["release_date"]).groupby("tkey").release_date.apply(list).to_dict()
    film["tkey"] = film.title.map(key)
    fb = [(not sp) and any(abs((r - rw).days) <= 120 for r in ann_rel.get(k, []))
          for sp, k, rw in zip(film.is_spanish, film.tkey, film.release_weekend)]
    film.loc[fb, "is_spanish"] = True
    qa.append(f"Top25 films flagged Spanish via weekly list: {int(sp_film.sum())}; via annual-list fallback: {sum(fb)}")
    film["origin"] = film.is_spanish.map({True: "Spanish", False: "Foreign"})

    film["legs_multiple"] = (film.total_gross_eur / film.opening_gross_eur).round(2)
    film["opening_per_screen_eur"] = (film.opening_gross_eur / film.opening_screens).round(0)
    film["avg_ticket_eur"] = (film.total_gross_eur / film.total_admissions).round(2)
    film["release_year"] = film.release_weekend.dt.year
    film["release_month_num"] = film.release_weekend.dt.month
    film["release_month"] = film.release_weekend.dt.strftime("%b")
    film["release_season"] = [season(d.date()) for d in film.release_weekend]
    film["opening_per_cinema_eur"] = (film.opening_gross_eur / film.opening_cinemas).round(0)
    film["opening_cinemas_band"] = pd.cut(film.opening_cinemas, [0, 49, 149, 249, 324, 10_000],
                                          labels=["1) <50", "2) 50-149", "3) 150-249", "4) 250-324",
                                                  "5) 325+"]).astype(str).replace("nan", "")
    film["gross_band"] = pd.cut(film.total_gross_eur, [-1, 1e6, 5e6, 10e6, 20e6, 1e12],
                                labels=["<1M", "1-5M", "5-10M", "10-20M", "20M+"]).astype(str)
    film = film.sort_values(["release_weekend", "title"]).reset_index(drop=True)
    film["film_id"] = [f"F{i:05d}" for i in range(1, len(film) + 1)]
    t = t.merge(film[["cluster", "film_id"]], on="cluster")

    # --- distributors dimension (all sources)
    dists = sorted(set(t.distributor) | set(s.distributor) | set(a.distributor))
    dim_dist = pd.DataFrame({"distributor": dists})
    dim_dist["distributor_type"] = dim_dist.distributor.map(lambda d: "Major studio" if d in MAJORS else
                                                            "Self-distributed" if d == "Self-distributed" else
                                                            "Unknown" if d == "Unknown" else "Independent")

    # --- write
    dim_film = film[["film_id", "title", "original_title", "distributor", "origin", "release_weekend",
                     "release_year", "release_month_num", "release_month", "release_season",
                     "is_rerelease", "opened_in_top25", "opening_gross_eur", "opening_admissions",
                     "opening_screens", "opening_cinemas", "opening_cinemas_band", "opening_rank",
                     "opening_per_screen_eur", "opening_per_cinema_eur", "total_gross_eur",
                     "total_admissions", "avg_ticket_eur", "legs_multiple", "weeks_in_top25",
                     "last_weeks_on_release", "peak_screens", "best_rank", "gross_band"]].copy()
    dim_film["release_weekend"] = dim_film.release_weekend.dt.date
    dim_film.to_csv(CLEAN / "dim_film.csv", index=False)

    fact_t = t[["film_id", "weekend_start", "rank", "weeks_on_release", "cinemas", "screens",
                "gross_eur", "admissions", "admissions_imputed", "gross_pct_change", "admissions_pct_change",
                "gross_cum_eur", "admissions_cum", "source_file"]].copy()
    fact_t["weekend_start"] = fact_t.weekend_start.dt.date
    fact_t.sort_values(["weekend_start", "rank"]).to_csv(CLEAN / "fact_weekend_top25.csv", index=False)

    fact_s = s[["weekend_start", "title", "distributor", "rank", "weeks_on_release", "cinemas", "screens",
                "gross_eur", "admissions", "admissions_imputed", "gross_cum_eur", "admissions_cum",
                "release_weekend",
                "source_file"]].copy()
    fact_s["weekend_start"] = fact_s.weekend_start.dt.date
    fact_s["release_weekend"] = fact_s.release_weekend.dt.date
    fact_s.sort_values(["weekend_start", "rank"]).to_csv(CLEAN / "fact_weekend_spanish.csv", index=False)

    a["year"] = a.year.astype(int)
    a["is_partial_year"] = a.year.eq(2026)
    a["released_in_year"] = a.release_date.dt.year.eq(a.year)
    fact_a = a[["year", "rank", "title", "distributor", "release_date", "released_in_year",
                "gross_eur", "admissions", "is_partial_year", "source_file"]].copy()
    fact_a["release_date"] = fact_a.release_date.dt.date
    fact_a.to_csv(CLEAN / "fact_annual_spanish.csv", index=False)

    dim_dist.to_csv(CLEAN / "dim_distributor.csv", index=False)
    build_dim_date().to_csv(CLEAN / "dim_date.csv", index=False)

    # --- QA checks
    neg = int((fact_t.gross_eur < 0).sum())
    cum_bad = int((fact_t.gross_cum_eur < fact_t.gross_eur).sum())
    rank_dupes = int(fact_t.duplicated(["weekend_start", "rank"]).sum())
    ticket = fact_t.gross_eur / fact_t.admissions
    qa += [
        f"Clean rows: fact_weekend_top25={len(fact_t)}, fact_weekend_spanish={len(fact_s)}, "
        f"fact_annual_spanish={len(fact_a)}, dim_film={len(dim_film)}, dim_distributor={len(dim_dist)}",
        f"Negative weekend gross: {neg}",
        f"Rows where cumulative gross < weekend gross: {cum_bad}",
        f"Duplicate (weekend, rank) pairs in Top 25: {rank_dupes}",
        f"Implied ticket price (gross/admissions) range: {ticket.min():.2f} - {ticket.max():.2f} EUR "
        f"(median {ticket.median():.2f})",
        f"Films whose first Top-25 appearance is not week 1 (opened outside Top 25): "
        f"{int((~film.opened_in_top25).sum())}",
        f"Re-releases flagged: {int(film.is_rerelease.sum())}",
    ]
    (CLEAN / "data_quality_report.md").write_text(
        "# Data quality report\n\n" + "\n".join(f"- {q}" for q in qa) + "\n", encoding="utf-8")
    print("\n".join(qa))


if __name__ == "__main__":
    main()
