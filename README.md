**English** | [Español](README.es.md)

# Spain Box Office 2020–2026: When, How Wide and What to Release

*Google Data Analytics – Case Study 3 (own case study). Tools: Python (pdfplumber, pandas), SQL (DuckDB), Power BI.*

## 1. Business task (Ask)

**Client:** an independent Spanish film distributor planning its release slate for the next two years.

**Business task:** *Identify which release windows, release widths and film origins (Spanish vs foreign) give a
film the best box-office outcome in Spain after COVID, and benchmark how independent distributors perform
against the Hollywood majors, so the client can decide when, how wide and what to release.*

| | |
|---|---|
| **Stakeholders** | Distributor's CEO and acquisitions team (what to buy), marketing/booking team (when and how wide to release) |
| **Audience** | Non-technical executives: a 30-minute presentation backed by an interactive Power BI report |
| **Key metrics** | Weekend gross (EUR), admissions, average ticket price, opening weekend, lifetime gross, *legs* (lifetime ÷ opening), hit rate (share of films grossing ≥ 1 M EUR), week-over-week drop, share of gross by origin and distributor type |
| **Questions** | 1) How big is the market and has it recovered? 2) When should a film be released? 3) Are Spanish films a good bet, and how do Spanish and foreign releases compare? 4) How do independents compare with majors? 5) How wide should a film open? |

## 2. Data sources (Prepare)

| Source | Content | Coverage | Files |
|---|---|---|---|
| ICAA (Ministerio de Cultura): [Taquilla y espectadores](https://www.cultura.gob.es/cultura/areas/cine/datos/taquilla-espectadores.html), weekly **Top 25** | Rank, Spanish and original title, distributor, weeks on release, cinemas, screens, weekend gross and admissions, % change, cumulative gross and admissions | 341 weekends, Jan 2020 – 15 Nov 2026 | 343 PDFs |
| ICAA weekly **Spanish films on release** | Same fields, every Spanish film on release (not only the Top 25) | 337 weekends, 2020–2026 | 337 PDFs |
| ICAA annual **Spanish films gross and admissions** | Every Spanish film per calendar year, with release date | 2016–2025 + 2026 YTD | 11 PDFs |

* Figures are produced by Comscore (Rentrak) and published by the ICAA. The ICAA notes they are not its official statistic.
* **ROCCC:** *Reliable*: industry-standard measurement, published by a government body. *Original*: a primary source. *Comprehensive*: complete weekly coverage, although the Top 25 excludes the long tail. *Current*: to November 2026. *Cited*: every row keeps its source file.
* **Licensing and privacy:** public government information, reusable with attribution (Ley 37/2007). It contains no personal data.
* Raw PDFs are in `data/raw/icaa/` and are never modified. `manifest.csv` records the URL and download time of every file.
* **Validation against an independent official figure:** the 2023 annual list gives 81.5 M EUR and 13.2 M admissions for Spanish films. The Ministry's press release reports 82.4 M EUR and 13.4 M, a gap of about 1%.

**Known limitations**
* The Top 25 is not the whole market. Its share is very high on most weekends, but long-tail films are missing from the weekly market totals.
* Films released before Jan 2020 that were still on release (e.g. *El rey león*) appear with incomplete opening data and are excluded from the new-release metrics.
* There is no data on genre, budget or marketing spend (see section 6).
* The source stopped reporting **screens** in June 2026, so **cinemas** is used as the measure of release width.

## 3. Cleaning and transformation (Process)

Reproducible pipeline: run `py scripts/01_download_icaa.py` … `05_build_pbip.py` in order.

**Running it yourself.** The raw PDFs (154 MB) are not in the repository; `01_download_icaa.py` downloads them again. The cleaned CSVs in `data/clean/` are included, so the Power BI report works without running the pipeline.
1. `py -m pip install -r requirements.txt`
2. Run the scripts in order. `05_build_pbip.py` rewrites the `DataFolder` parameter with your local path.
3. If you only open the Power BI project, set `DataFolder` under *Transform data → Edit parameters* to your `data/clean/` folder (with a trailing backslash), then click **Refresh**.

| Step | Script | What it does |
|---|---|---|
| Download | `01_download_icaa.py` | Scrapes the ICAA page and downloads 701 PDFs with retries, a polite delay and a manifest |
| Extract | `02_extract_tables.py` | Only the header row is ruled in the PDFs. The script takes the column boundaries from the header and assigns each word to a row and column by its coordinates |
| Clean and model | `03_clean_model.py` | Cleans the data and builds the star schema in `data/clean/` |
| Analyze | `04_analysis.py` + `sql/analysis.sql` | 17 DuckDB SQL queries, results in `analysis/*.csv` |
| Dashboard | `05_build_pbip.py` | Generates the Power BI project (`powerbi/`) |

**Issues found and how each was handled** (`data/clean/data_quality_report.md` has the counts):

1. **Dates were not in the PDFs.** Files from 2020–21 had no year in the file name (`top25-26-28-febrero.pdf`). The year was inferred because the weekend must start on a Friday, which picks out a single year between 2020 and 2023. Single-date names (`25enero` = Saturday) and month-spanning names (`30-1-agosto`) were also handled.
2. **Mislabelled files.** Two file names had the wrong month (`27-29-diciembre` is really 27–29 Nov 2020). These were found and fixed by checking the films' *weeks on release* against neighbouring weekends. Links with the wrong label on the ICAA page, and typos such as `espaniol` and `epaniol`, were reclassified by file name.
3. **Errors in the source.** Two weekends had a broken admissions column: 3–5 Feb 2023 (admissions truncated) and 14–16 Jun 2024 (values repeated from row 7). These were detected through an implausible implied ticket price, outside 4–12 EUR for a file's median or 3–30 EUR for a row. 28 rows were rebuilt from the difference in cumulative admissions, and 23 were estimated from that weekend's median ticket price. All are flagged in `admissions_imputed`.
4. **Overlapping PDF text** garbled 19 rows (6 films with very long original titles). They were fixed with a manual mapping.
5. **Inconsistent names.** 393 distributor spellings were reduced to 318 canonical names (`WBI`/`Warner Bros Int'l` → *Warner Bros*, `ACONTRA` → *A Contracorriente*…), each classified as *Major studio*, *Independent* or *Self-distributed*. Titles were standardised (`Working Man, A` → `A Working Man`).
6. **Film identity.** Weekly rows were linked into 2,250 film releases when they share either the original title or the Spanish title (for example, "Inside Out 2" and "Del Revés 2 (Inside out 2)"). They were then split by release date so re-releases and remakes stay separate. 92 re-releases are flagged.
7. **Spanish origin.** A film is Spanish if it appears in the ICAA list of Spanish films on release that same weekend (553 films), or in the annual list (7 more).
8. Partial-year snapshots superseded by full-year files were dropped. Missing screens are left as null, not zero. No duplicates were found per weekend and rank.

**Star schema:** `fact_weekend_top25` (8,525 rows) · `fact_weekend_spanish` (10,304) · `fact_annual_spanish` (4,832) · `dim_film` (2,250) · `dim_distributor` (318) · `dim_date` (2016–2026, with season, Easter and Christmas windows and COVID period).

## 4. Analysis summary (Analyze)

The comparisons cover **post-COVID new releases (2022–2026)** that opened in the Top 25, excluding re-releases (1,607 films). All figures come from `analysis/`.

**Market (q01, q07).** Top 25 gross plateaued at 276–286 M EUR in 2023–2025. 2026 has already reached **320 M EUR in 46 weekends**, the best year in the series: average weekend gross is +31% on 2025. Until 2026, growth came from **price, not audience**: the average ticket rose from 7.04 EUR (2023) to 7.82 EUR (2026, +11%) while admissions stayed flat at 37–41 M. The market is very concentrated: the 10 biggest films take **34–47%** of the year's Top 25 gross, and the top 20% of films take 83–89%.

**Timing (q02, q03, q10, q11).** Demand peaks in **July** (7.0 M EUR per weekend) and **December** (6.3 M); February and September are the weakest months (4.8–4.9 M). Supply matters as much as demand, though:
* Films released in **December** have the best median lifetime gross (376k EUR), hit rate (30%) and legs (3.4x). October (294k) and February (330k) come next.
* **May–July releases have the lowest medians** (53–87k EUR). Summer demand goes to the majors' blockbusters.
* Weekends with **9 or more new entries** cut the median opening to 30–40k EUR, against 60–126k with 4–6 new entries.

**Spanish vs foreign (q04, q09, q10).** Spanish films match foreign ones on median opening (62k EUR each) and median lifetime gross (165k vs 151k). They hold slightly better: legs 2.44 vs 2.35, and weeks 5–8 drop 31–37% against 38–43%. Hits are rarer, though: a 19% hit rate against 24%. Release season changes the picture:
* **Spanish summer releases** outperform: median 258k EUR and a 28% hit rate, against 72k for foreign summer films. These are family comedies such as *Padre no hay más que uno*.
* **Spanish spring releases** are the weakest segment: median 68k EUR and an 8% hit rate.

The Spanish share of Top 25 gross ranges from 15% to 24% depending on a few hits.

**Spanish vs foreign releases in depth (q15–q17).**
* **Volume vs money.** Spanish films are about 26–30% of new releases but earned only about 16–17% of release gross in 2023–2025. In 2026 that rose to 25%, thanks to *La bola negra* and *Torrente, presidente*.
* **At equal opening width.** Up to 249 cinemas, Spanish films earn as much as foreign ones or more (median 276k vs 248k EUR at 150–249 cinemas). Above 250 cinemas they earn less (2.98 M vs 6.05 M EUR at 325+) and less per cinema, but they hold longer (legs 4.8x vs 4.0x). So Spanish films underperform mainly because few are opened wide, not because they do worse at a given width.
* **Who releases them.** Majors release only 23% of Spanish films (100 of 437) but take 61% of their gross. Independents take 39% of Spanish-film gross, against 13% of foreign-film gross: Spanish cinema is where independents really compete.

**Distributors (q05, q06).** The majors take 76–89% of Top 25 gross, but the **independent share has doubled, from 11% (2022) to 24% (2026)**. Independents differ widely:
* **Elastica** (66.8 M EUR, 26% hit rate, legs 3.4) and **Beta Fiction** (35% hit rate) run a few, wide, commercial releases.
* **A Contracorriente** (136 films, 6.6% hit rate) and **Filmax** (83 films, 2.4%) run high-volume arthouse and genre slates.

**Release width (q08).** Outcomes jump at about **250 cinemas**:
* Hit rate goes from 11% (150–249 cinemas) to 53% (250–324) and 96% (325+).
* Opening gross *per cinema* doubles: 563 EUR → 1,148 EUR → 3,301 EUR.
* Legs rise from 2.3x to 3.1x and then 4.1x.

*Caveat:* this is correlation. Distributors open wide the films they already expect to perform.

## 5. Visualizations (Share)

Power BI project: `powerbi/SpainBoxOffice.pbip`. Open it in Power BI Desktop and click **Refresh**. The data path is the `DataFolder` parameter, under *Transform data → Edit parameters*.

| Page | Answers |
|---|---|
| 1. Market Overview | KPIs, annual gross by origin, monthly recovery curve, majors vs independents, concentration, ticket price |
| 2. Release Timing | Demand by calendar month, outcome by release month, release-window scorecard, hit rate by month |
| 3. Spanish Cinema | Spanish vs foreign scorecard, weekly drop curves, Spanish cinema 2016–2026, biggest films |
| 3b. Spanish vs Foreign | Share of releases vs share of gross by year, results at equal opening width, majors vs independents by origin |
| 4. Distributors | Distributor league table, type share by year, hit rate by distributor |
| 5. Release Strategy | Opening width vs gross, hit rate and legs by width band, film-level scatter |

The model has 26 DAX measures, including hit rate, Spanish share of releases and of gross, median legs, week-over-week drop, top-10 concentration and YoY %. Visual theme: Spanish red and navy.

The year slicers on every page list only years after 2019. They don't remove from the totals the 2019 films still showing in early 2020.

## 6. Recommendations and next steps (Act)

**Top insights for the client**
1. **Release fewer films, but wider.** Below ~150 cinemas almost no film reaches 1 M EUR. Put marketing behind titles that can open in at least 250 cinemas, and release the rest as platform or arthouse releases with low print and advertising spend.
2. **Release in under-supplied windows.** December, October and February give the best results per film. Avoid May–July unless the title is a Spanish family comedy, and avoid weekends with 9 or more openings.
3. **Spanish commercial cinema is a competitive bet.** It has the same median gross as foreign films, better legs and a summer niche the majors don't serve. Elastica's and Beta Fiction's model (few, wide, commercial Spanish titles) beats the high-volume model.
4. **Plan for legs.** Spanish films hold better after week 4. Negotiate to keep screens rather than accepting a fast drop.
5. **Price-driven growth is fragile.** Admissions are flat, so event releases and audience building matter more than ticket price.

**Further deliverables to expand the analysis**
* Add **genre, runtime, cast and director** (Wikidata or TMDB) to test what drives hits.
* Add the official **annual market totals** (ICAA statistics) to measure the Top 25's coverage.
* Add **budget and marketing spend** (if the client has them) to measure ROI by release width.
* Build a **predictive model** of lifetime gross from opening weekend, width and season.
* Add **regional and cinema-chain** data, and streaming windows, to optimise booking.

---
*Folder layout:* `data/raw` (PDFs + manifest) · `data/interim` (raw extraction) · `data/clean` (model + QA report) · `sql/` · `analysis/` · `scripts/` · `powerbi/`.
