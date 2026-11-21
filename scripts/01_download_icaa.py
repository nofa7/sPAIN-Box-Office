"""Step 1 (Prepare): download ICAA box-office PDFs (Rentrak/Comscore data).

Source page: https://www.cultura.gob.es/cultura/areas/cine/datos/taquilla-espectadores.html
Writes PDFs to data/raw/icaa/<category>/ and a manifest CSV (url, label, file, size, downloaded_at).
Re-running skips files already downloaded.
"""
import csv
import html
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "icaa"
PAGE = "https://www.cultura.gob.es/cultura/areas/cine/datos/taquilla-espectadores.html"
UA = {"User-Agent": "Mozilla/5.0 (data-analytics case study)"}


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def categorize(url: str, label: str) -> str:
    u, l = url.lower(), label.lower()
    if "internacional" in u or "internacional" in l:
        return "annual_international"
    if "top-25" in u or "top25" in u or l.startswith("top 25"):
        return "weekly_top25"
    if "topespanol" in u or "cine español en cartelera" in l or "cine español:" in l:
        return "weekly_spanish"
    if "acumulado" in u or "recaudaci" in u or "acumulado" in l or "recaudación" in l:
        return "annual_spanish"
    return "other"


def main() -> None:
    page = fetch(PAGE).decode("utf-8", errors="replace")
    links = re.findall(r'<a[^>]+href="([^"]+\.pdf)"[^>]*>(.*?)</a>', page, flags=re.S | re.I)
    seen, items = set(), []
    for href, inner in links:
        url = urllib.parse.urljoin(PAGE, html.unescape(href))
        if url in seen:
            continue
        seen.add(url)
        label = re.sub(r"<[^>]+>", "", html.unescape(inner))
        label = re.sub(r"\s+", " ", label).strip()
        items.append((url, label, categorize(url, label)))
    print(f"{len(items)} PDF links found", flush=True)

    manifest = RAW / "manifest.csv"
    RAW.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, (url, label, cat) in enumerate(items, 1):
        dest_dir = RAW / cat
        dest_dir.mkdir(parents=True, exist_ok=True)
        jcr = re.search(r"jcr:([0-9a-f]{8})", url)
        name = url.rsplit("/", 1)[-1]
        fname = f"{jcr.group(1)}_{name}" if jcr else name
        dest = dest_dir / fname
        if not dest.exists():
            for attempt in range(3):
                try:
                    data = fetch(url)
                    if not data.startswith(b"%PDF"):
                        raise ValueError("not a PDF")
                    dest.write_bytes(data)
                    break
                except Exception as e:  # noqa: BLE001
                    print(f"  retry {attempt+1} {url}: {e}", file=sys.stderr)
                    time.sleep(2 * (attempt + 1))
            time.sleep(0.3)  # be polite to the server
        ok = dest.exists()
        rows.append({
            "url": url, "label": label, "category": cat,
            "file": dest.relative_to(ROOT).as_posix() if ok else "",
            "bytes": dest.stat().st_size if ok else 0,
            "downloaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
        if i % 50 == 0:
            print(f"  {i}/{len(items)}", flush=True)

    with manifest.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    failed = [r for r in rows if not r["file"]]
    print(f"done: {len(rows) - len(failed)} ok, {len(failed)} failed -> {manifest}")


if __name__ == "__main__":
    main()
