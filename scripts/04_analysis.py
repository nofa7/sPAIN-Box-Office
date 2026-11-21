"""Step 4 (Analyze): run sql/analysis.sql with DuckDB over data/clean/*.csv.
Each query (introduced by '-- name: <id>') is saved to analysis/<id>.csv and echoed to stdout.
"""
import re
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean"
OUT = ROOT / "analysis"


def main():
    OUT.mkdir(exist_ok=True)
    con = duckdb.connect()
    for csv in CLEAN.glob("*.csv"):
        con.execute(f"CREATE VIEW {csv.stem} AS SELECT * FROM read_csv_auto('{csv.as_posix()}', header=true)")
    sql = (ROOT / "sql" / "analysis.sql").read_text(encoding="utf-8")
    blocks = re.split(r"^-- name:\s*", sql, flags=re.M)[1:]
    for block in blocks:
        name, body = block.split("\n", 1)
        df = con.execute(body).df()
        df.to_csv(OUT / f"{name.strip()}.csv", index=False)
        print(f"\n=== {name.strip()}\n{df.to_string(index=False)}")


if __name__ == "__main__":
    main()
